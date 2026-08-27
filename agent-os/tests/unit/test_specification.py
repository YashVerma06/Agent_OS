from __future__ import annotations

import json
from typing import Any

import pytest

from app.agents.discovery_conversation import build_discovery_context
from app.contracts import WorkflowSnapshot, WorkflowState
from app.services.specification import (
    REQUIRED_SECTIONS,
    DiscoveryRecord,
    SpecificationDraft,
    StructuredGenerationError,
    build_discovery_record,
    build_specification_draft,
    render_specification,
    validate_specification,
)
from app.services.transcript import (
    InMemoryTranscriptStore,
    Speaker,
    UtteranceSource,
)


class FakeGenerator:
    """Records prompts and replays canned payloads. Never touches the network."""

    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self._payloads = list(payloads)
        self.prompts: list[str] = []
        self.instructions: list[str] = []

    def generate_json(self, *, prompt: str, instruction: str) -> dict[str, Any]:
        self.prompts.append(prompt)
        self.instructions.append(instruction)
        return self._payloads.pop(0)


RECORD_PAYLOAD = {
    "confirmed_decisions": ["Tenants submit maintenance requests through a form."],
    "assumptions": ["Managers are internal staff with accounts."],
    "unresolved_questions": ["Are photo uploads required for the first release?"],
    "topics_covered": ["users_and_roles", "workflows"],
    "topics_not_covered": ["integrations"],
    "client_quotes": ["We manage rental properties."],
}

SPEC_PAYLOAD = {
    "executive_summary": "A maintenance request portal for tenants and managers.",
    "problem_statement": "Requests arrive by phone and are lost.",
    "users_and_roles": [
        {"name": "Tenant", "description": "Submits requests", "permissions": ["create"]},
        {"name": "Manager", "description": "Triages requests", "permissions": ["read", "update"]},
    ],
    "in_scope": ["Request submission", "Status triage"],
    "out_of_scope": ["Payments", "Photo upload"],
    "functional_requirements": [
        {"statement": "A tenant can submit a request.", "acceptance": "Request is persisted."},
        {"statement": "A manager can change status.", "acceptance": "Status is updated."},
    ],
    "workflows": [
        {"name": "Submit request", "actor": "Tenant", "steps": ["Open form", "Submit"]}
    ],
    "data_model": [
        {"entity": "Request", "field": "severity", "type": "enum", "required": True, "notes": ""}
    ],
    "permissions": ["Only managers may change status."],
    "validation_rules": ["Email must be valid."],
    "non_functional_requirements": ["Responsive at 1440x900."],
    "acceptance_criteria": ["A tenant submits and a manager resolves a request."],
    "assumptions": ["No authentication in the first release."],
    "risks": ["Status values may diverge between UI and API."],
    "unresolved_questions": ["Are notifications required?"],
}


def context_fixture():
    return build_discovery_context(
        WorkflowSnapshot(
            workflow_id="wf-1",
            tenant_id="tenant-1",
            name="Maintenance Portal",
            client_request="We manage rental properties and need a maintenance portal.",
            client_name="Alpha Property Group",
            state=WorkflowState.DISCOVERY,
        )
    )


def transcript_fixture():
    store = InMemoryTranscriptStore()
    store.append(
        meeting_id="m-1",
        workflow_id="wf-1",
        speaker=Speaker.CLIENT,
        content="We manage rental properties.",
        source=UtteranceSource.LIVE_VOICE,
    )
    store.append(
        meeting_id="m-1",
        workflow_id="wf-1",
        speaker=Speaker.AGENT,
        content="Who uses this day to day?",
        source=UtteranceSource.LIVE_VOICE,
    )
    return store.finalize("m-1", "wf-1")


# ------------------------------------------------------- discovery record -- #


def test_discovery_record_separates_decisions_assumptions_and_questions() -> None:
    generator = FakeGenerator([RECORD_PAYLOAD])
    record = build_discovery_record(
        context=context_fixture(), transcript=transcript_fixture(), generator=generator
    )

    assert record.confirmed_decisions == RECORD_PAYLOAD["confirmed_decisions"]
    assert record.assumptions == RECORD_PAYLOAD["assumptions"]
    assert record.unresolved_questions == RECORD_PAYLOAD["unresolved_questions"]
    assert record.workflow_id == "wf-1"
    assert record.meeting_id == "m-1"


def test_discovery_record_prompt_contains_the_transcript_only() -> None:
    generator = FakeGenerator([RECORD_PAYLOAD])
    build_discovery_record(
        context=context_fixture(), transcript=transcript_fixture(), generator=generator
    )
    prompt = generator.prompts[0]
    assert "We manage rental properties." in prompt
    assert "Who uses this day to day?" in prompt


def test_discovery_record_tolerates_a_sparse_model_response() -> None:
    generator = FakeGenerator([{}])
    record = build_discovery_record(
        context=context_fixture(), transcript=transcript_fixture(), generator=generator
    )
    assert record.confirmed_decisions == []
    assert record.unresolved_questions == []


def test_discovery_record_serializes_to_json() -> None:
    generator = FakeGenerator([RECORD_PAYLOAD])
    record = build_discovery_record(
        context=context_fixture(), transcript=transcript_fixture(), generator=generator
    )
    assert json.loads(record.as_json())["workflow_id"] == "wf-1"


# --------------------------------------------------------- specification --- #


def test_requirements_receive_stable_ids() -> None:
    draft = SpecificationDraft.model_validate(SPEC_PAYLOAD).with_requirement_ids()
    assert [item.requirement_id for item in draft.functional_requirements] == [
        "FR-001",
        "FR-002",
    ]


def test_supplied_requirement_ids_are_preserved() -> None:
    payload = dict(SPEC_PAYLOAD)
    payload["functional_requirements"] = [
        {"requirement_id": "FR-042", "statement": "Custom", "acceptance": "Yes"}
    ]
    draft = SpecificationDraft.model_validate(payload).with_requirement_ids()
    assert draft.functional_requirements[0].requirement_id == "FR-042"


def test_rendered_specification_contains_every_required_section() -> None:
    generator = FakeGenerator([SPEC_PAYLOAD])
    context = context_fixture()
    record = DiscoveryRecord(workflow_id="wf-1", meeting_id="m-1")
    draft = build_specification_draft(context=context, record=record, generator=generator)
    markdown = render_specification(context=context, record=record, draft=draft)

    for section in REQUIRED_SECTIONS:
        assert f"## {section}" in markdown, section
    assert validate_specification(markdown) == []


def test_rendered_specification_is_client_agnostic() -> None:
    """No hardcoded demo client may leak into the renderer."""
    generator = FakeGenerator([SPEC_PAYLOAD])
    context = context_fixture()
    record = DiscoveryRecord(workflow_id="wf-1", meeting_id="m-1")
    draft = build_specification_draft(context=context, record=record, generator=generator)
    markdown = render_specification(context=context, record=record, draft=draft)

    assert "Northstar" not in markdown
    assert "Alpha Property Group" in markdown


def test_specification_records_lineage_back_to_the_meeting() -> None:
    context = context_fixture()
    record = DiscoveryRecord(workflow_id="wf-1", meeting_id="m-1")
    markdown = render_specification(
        context=context, record=record, draft=SpecificationDraft.model_validate(SPEC_PAYLOAD)
    )
    assert "m-1" in markdown
    assert "wf-1" in markdown


def test_empty_draft_still_renders_all_sections_and_flags_gaps() -> None:
    """A thin conversation must produce an honest document, not a fabricated one."""
    context = context_fixture()
    record = DiscoveryRecord(workflow_id="wf-1", meeting_id="m-1")
    markdown = render_specification(
        context=context, record=record, draft=SpecificationDraft()
    )

    for section in REQUIRED_SECTIONS:
        assert f"## {section}" in markdown, section
    assert "Not established during discovery" in markdown

    problems = validate_specification(markdown)
    assert problems == ["no identified functional requirements (expected FR-### ids)"]


def test_validation_reports_a_missing_section() -> None:
    markdown = "# SPECIFICATIONS.md\n\n## Executive summary\n\nSomething.\n"
    problems = validate_specification(markdown)
    assert any("missing section: Problem statement" in item for item in problems)


def test_validation_reports_an_empty_section() -> None:
    context = context_fixture()
    record = DiscoveryRecord(workflow_id="wf-1", meeting_id="m-1")
    markdown = render_specification(
        context=context, record=record, draft=SpecificationDraft.model_validate(SPEC_PAYLOAD)
    )
    hollowed = markdown.replace(
        "Requests arrive by phone and are lost.", ""
    )
    assert any("empty section: Problem statement" in item for item in
               validate_specification(hollowed))


def test_generation_rejects_a_non_object_response() -> None:
    class BadGenerator:
        def generate_json(self, *, prompt: str, instruction: str) -> Any:
            return ["not", "an", "object"]

    with pytest.raises(StructuredGenerationError):
        build_specification_draft(
            context=context_fixture(),
            record=DiscoveryRecord(workflow_id="wf-1", meeting_id="m-1"),
            generator=BadGenerator(),
        )

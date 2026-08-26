"""Post-meeting structured generation: DISCOVERY_RECORD and SPECIFICATIONS.

The live voice session never becomes the specification directly. A spoken
conversation is evidence; the specification is a separate, reviewable document
generated from that evidence in one deliberate pass.

The split here matters: the model produces *structured data*, and deterministic
code renders the markdown. That way section completeness is a property of the
renderer rather than a hope about the model, and `validate_specification` can
fail loudly when a required section is empty.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import BaseModel, Field

from app.agents.discovery import EngagementContext
from app.services.transcript import TranscriptDocument, transcript_as_dialogue

# Section titles, in render order. `validate_specification` checks all of them.
REQUIRED_SECTIONS: tuple[str, ...] = (
    "Executive summary",
    "Problem statement",
    "Users and roles",
    "Scope",
    "Functional requirements",
    "Workflows",
    "Data model",
    "Permissions",
    "Validation",
    "Non-functional requirements",
    "Acceptance criteria",
    "Assumptions",
    "Risks",
    "Exclusions",
    "Unresolved questions",
)


class StructuredGenerationError(RuntimeError):
    pass


class StructuredGenerator(Protocol):
    """Injectable so tests never reach the network."""

    def generate_json(self, *, prompt: str, instruction: str) -> dict[str, Any]:
        ...


class UserRole(BaseModel):
    name: str
    description: str = ""
    permissions: list[str] = Field(default_factory=list)


class FunctionalRequirement(BaseModel):
    requirement_id: str = ""
    statement: str
    rationale: str = ""
    acceptance: str = ""


class WorkflowStep(BaseModel):
    name: str
    actor: str = ""
    steps: list[str] = Field(default_factory=list)


class DataField(BaseModel):
    entity: str
    field: str
    type: str = "string"
    required: bool = True
    notes: str = ""


class DiscoveryRecord(BaseModel):
    """Evidence extracted from the transcript, before it becomes a specification."""

    workflow_id: str
    meeting_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: str = "agent_os_meeting_room"
    confirmed_decisions: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    topics_covered: list[str] = Field(default_factory=list)
    topics_not_covered: list[str] = Field(default_factory=list)
    client_quotes: list[str] = Field(default_factory=list)

    def as_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), indent=2, ensure_ascii=False)


class SpecificationDraft(BaseModel):
    executive_summary: str = ""
    problem_statement: str = ""
    users_and_roles: list[UserRole] = Field(default_factory=list)
    in_scope: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    functional_requirements: list[FunctionalRequirement] = Field(default_factory=list)
    workflows: list[WorkflowStep] = Field(default_factory=list)
    data_model: list[DataField] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    validation_rules: list[str] = Field(default_factory=list)
    non_functional_requirements: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)

    def with_requirement_ids(self) -> SpecificationDraft:
        """Assign stable FR-### ids to any requirement the model left unnumbered."""
        numbered: list[FunctionalRequirement] = []
        for index, requirement in enumerate(self.functional_requirements, start=1):
            existing = requirement.requirement_id.strip()
            numbered.append(
                requirement.model_copy(
                    update={"requirement_id": existing or f"FR-{index:03d}"}
                )
            )
        return self.model_copy(update={"functional_requirements": numbered})


DISCOVERY_RECORD_INSTRUCTION = """
You extract structured discovery evidence from a transcript. Return JSON only.

Separate three things and never blur them:
  - confirmed_decisions: the client stated this explicitly
  - assumptions: you inferred it and a human should confirm it
  - unresolved_questions: it was raised and not settled, or never came up

Quote the client verbatim in client_quotes for the decisions that matter.
Do not invent requirements the transcript does not support. A short, honest
record with many unresolved questions is correct when the conversation was
short.

JSON shape:
{"confirmed_decisions": [str], "assumptions": [str], "unresolved_questions": [str],
 "topics_covered": [str], "topics_not_covered": [str], "client_quotes": [str]}
""".strip()

SPECIFICATION_INSTRUCTION = """
You turn discovery evidence into a software specification. Return JSON only.

Every functional requirement must be independently testable and traceable to
the transcript or to a stated assumption. Do not pad. If the evidence does not
support a section, leave it sparse and add the gap to unresolved_questions
instead of inventing content.

Never include pricing, contractual terms, delivery dates, or legal commitments.

JSON shape:
{"executive_summary": str, "problem_statement": str,
 "users_and_roles": [{"name": str, "description": str, "permissions": [str]}],
 "in_scope": [str], "out_of_scope": [str],
 "functional_requirements": [{"requirement_id": str, "statement": str,
   "rationale": str, "acceptance": str}],
 "workflows": [{"name": str, "actor": str, "steps": [str]}],
 "data_model": [{"entity": str, "field": str, "type": str, "required": bool, "notes": str}],
 "permissions": [str], "validation_rules": [str], "non_functional_requirements": [str],
 "acceptance_criteria": [str], "assumptions": [str], "risks": [str],
 "unresolved_questions": [str]}
""".strip()


def build_discovery_record(
    *,
    context: EngagementContext,
    transcript: TranscriptDocument,
    generator: StructuredGenerator,
) -> DiscoveryRecord:
    dialogue = transcript_as_dialogue(transcript.utterances)
    prompt = (
        f"{context.as_prompt_block()}\n\n"
        f"Transcript of the discovery meeting ({transcript.utterance_count} utterances):\n"
        f"{dialogue or '(no spoken utterances were captured)'}"
    )
    payload = generator.generate_json(
        prompt=prompt, instruction=DISCOVERY_RECORD_INSTRUCTION
    )
    if not isinstance(payload, dict):
        raise StructuredGenerationError("Discovery record generation returned a non-object.")

    return DiscoveryRecord(
        workflow_id=context.workflow_id,
        meeting_id=transcript.meeting_id,
        confirmed_decisions=_string_list(payload.get("confirmed_decisions")),
        assumptions=_string_list(payload.get("assumptions")),
        unresolved_questions=_string_list(payload.get("unresolved_questions")),
        topics_covered=_string_list(payload.get("topics_covered")),
        topics_not_covered=_string_list(payload.get("topics_not_covered")),
        client_quotes=_string_list(payload.get("client_quotes")),
    )


def build_specification_draft(
    *,
    context: EngagementContext,
    record: DiscoveryRecord,
    generator: StructuredGenerator,
) -> SpecificationDraft:
    prompt = (
        f"{context.as_prompt_block()}\n\n"
        f"Discovery evidence:\n{record.as_json()}"
    )
    payload = generator.generate_json(
        prompt=prompt, instruction=SPECIFICATION_INSTRUCTION
    )
    if not isinstance(payload, dict):
        raise StructuredGenerationError("Specification generation returned a non-object.")
    return SpecificationDraft.model_validate(payload).with_requirement_ids()


def render_specification(
    *, context: EngagementContext, record: DiscoveryRecord, draft: SpecificationDraft
) -> str:
    """Render SPECIFICATIONS.md deterministically.

    Every required section is emitted whether or not the model filled it. An
    empty section renders an explicit gap marker, which is honest and which
    `validate_specification` can then flag.
    """
    draft = draft.with_requirement_ids()
    client = context.client_name or "Not supplied"
    lines: list[str] = [
        "# SPECIFICATIONS.md",
        "",
        f"- Engagement: {context.project_name}",
        f"- Client: {client}",
        f"- Workflow: `{context.workflow_id}`",
        f"- Tenant: `{context.tenant_id}`",
        f"- Discovery source: Agent OS Meeting Room transcript `{record.meeting_id}`",
        f"- Generated: {record.generated_at.isoformat()}",
        "",
        "> Draft for human approval. No agent may approve this document, and the "
        "Builder cannot start until an authenticated human approves this exact "
        "SHA-256.",
        "",
        "## Executive summary",
        "",
        draft.executive_summary.strip() or _gap("no summary was derivable from the transcript"),
        "",
        "## Problem statement",
        "",
        draft.problem_statement.strip() or _gap("the problem was not stated explicitly"),
        "",
        "## Users and roles",
        "",
    ]

    if draft.users_and_roles:
        lines.append("| Role | Description | Permissions |")
        lines.append("|---|---|---|")
        for role in draft.users_and_roles:
            perms = ", ".join(role.permissions) or "not specified"
            lines.append(f"| {role.name} | {role.description or '-'} | {perms} |")
    else:
        lines.append(_gap("no roles were identified"))

    lines += ["", "## Scope", "", "**In scope**", ""]
    lines += _bullets(draft.in_scope, "nothing was confirmed as in scope")
    lines += ["", "**Out of scope**", ""]
    lines += _bullets(draft.out_of_scope, "no exclusions were confirmed")

    lines += ["", "## Functional requirements", ""]
    if draft.functional_requirements:
        lines.append("| ID | Requirement | Acceptance |")
        lines.append("|---|---|---|")
        for requirement in draft.functional_requirements:
            lines.append(
                f"| {requirement.requirement_id} | {requirement.statement} "
                f"| {requirement.acceptance or 'to be defined'} |"
            )
    else:
        lines.append(_gap("no testable requirements were derivable"))

    lines += ["", "## Workflows", ""]
    if draft.workflows:
        for flow in draft.workflows:
            actor = f" — {flow.actor}" if flow.actor else ""
            lines.append(f"**{flow.name}**{actor}")
            lines.append("")
            for index, step in enumerate(flow.steps, start=1):
                lines.append(f"{index}. {step}")
            lines.append("")
    else:
        lines.append(_gap("no end-to-end workflow was described"))

    lines += ["", "## Data model", ""]
    if draft.data_model:
        lines.append("| Entity | Field | Type | Required | Notes |")
        lines.append("|---|---|---|---|---|")
        for field in draft.data_model:
            required = "yes" if field.required else "no"
            lines.append(
                f"| {field.entity} | {field.field} | {field.type} | {required} "
                f"| {field.notes or '-'} |"
            )
    else:
        lines.append(_gap("no data fields were confirmed"))

    lines += ["", "## Permissions", ""]
    lines += _bullets(draft.permissions, "no permission rules were confirmed")
    lines += ["", "## Validation", ""]
    lines += _bullets(draft.validation_rules, "no validation rules were confirmed")
    lines += ["", "## Non-functional requirements", ""]
    lines += _bullets(
        draft.non_functional_requirements, "no non-functional constraints were raised"
    )
    lines += ["", "## Acceptance criteria", ""]
    lines += _bullets(draft.acceptance_criteria, "no measurable acceptance criteria were agreed")
    lines += ["", "## Assumptions", ""]
    lines += _bullets(
        draft.assumptions or record.assumptions, "no assumptions were recorded"
    )
    lines += ["", "## Risks", ""]
    lines += _bullets(draft.risks, "no risks were identified")
    lines += ["", "## Exclusions", ""]
    lines += _bullets(draft.out_of_scope, "no exclusions were confirmed")
    lines += ["", "## Unresolved questions", ""]
    lines += _bullets(
        draft.unresolved_questions or record.unresolved_questions,
        "no open questions were recorded, which is itself worth confirming",
    )
    lines.append("")
    return "\n".join(lines)


def validate_specification(markdown: str) -> list[str]:
    """Return the required sections that are missing or empty.

    An empty list means the document is structurally complete. It does not mean
    the content is good — that is what the human gate is for.
    """
    problems: list[str] = []
    for section in REQUIRED_SECTIONS:
        pattern = re.compile(rf"^##\s+{re.escape(section)}\s*$", re.MULTILINE)
        match = pattern.search(markdown)
        if match is None:
            problems.append(f"missing section: {section}")
            continue
        following = markdown[match.end() :]
        next_heading = re.search(r"^##\s+", following, re.MULTILINE)
        body = following[: next_heading.start()] if next_heading else following
        if not body.strip():
            problems.append(f"empty section: {section}")

    if not re.search(r"\bFR-\d{3}\b", markdown):
        problems.append("no identified functional requirements (expected FR-### ids)")
    return problems


def _bullets(values: list[str], empty_note: str) -> list[str]:
    if not values:
        return [_gap(empty_note)]
    return [f"- {value}" for value in values]


def _gap(note: str) -> str:
    return f"_Not established during discovery — {note}._"


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]

"""Meeting API integration tests.

These build their own FastAPI app around the router, because
`app/fast_api_app.py` is a shared file this branch does not modify. That also
keeps each test on isolated stores.

No test reaches Google. The structured generator is faked, and live voice stays
disabled, so the suite costs nothing to run.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api import meeting_routes
from app.contracts import ActorRole, TransitionRequest, WorkflowCreateRequest
from app.platform.artifacts import InMemoryArtifactStore
from app.platform.workflow import InMemoryWorkflowEngine
from app.services.live_meeting import (
    InMemoryMeetingStore,
    MeetingSettings,
)
from app.services.transcript import InMemoryTranscriptStore

RECORD_PAYLOAD = {
    "confirmed_decisions": ["Tenants submit maintenance requests."],
    "assumptions": ["Managers are internal staff."],
    "unresolved_questions": ["Are photo uploads needed?"],
    "topics_covered": ["users_and_roles"],
    "topics_not_covered": ["integrations"],
    "client_quotes": ["We manage rental properties."],
}

SPEC_PAYLOAD = {
    "executive_summary": "A maintenance request portal.",
    "problem_statement": "Requests are lost on the phone.",
    "users_and_roles": [{"name": "Tenant", "description": "Submits", "permissions": ["create"]}],
    "in_scope": ["Submission"],
    "out_of_scope": ["Payments"],
    "functional_requirements": [
        {"statement": "A tenant can submit a request.", "acceptance": "Persisted."}
    ],
    "workflows": [{"name": "Submit", "actor": "Tenant", "steps": ["Open", "Send"]}],
    "data_model": [
        {"entity": "Request", "field": "severity", "type": "enum", "required": True, "notes": ""}
    ],
    "permissions": ["Managers change status."],
    "validation_rules": ["Email must be valid."],
    "non_functional_requirements": ["Responsive."],
    "acceptance_criteria": ["Submit then resolve."],
    "assumptions": ["No auth initially."],
    "risks": ["Status divergence."],
    "unresolved_questions": ["Notifications?"],
}


class FakeGenerator:
    def __init__(self) -> None:
        self.calls = 0

    def generate_json(self, *, prompt: str, instruction: str) -> dict[str, Any]:
        self.calls += 1
        return RECORD_PAYLOAD if self.calls == 1 else SPEC_PAYLOAD


class Harness:
    def __init__(self) -> None:
        self.workflows = InMemoryWorkflowEngine()
        self.artifacts = InMemoryArtifactStore()
        self.meetings = InMemoryMeetingStore()
        self.transcripts = InMemoryTranscriptStore()
        self.generator = FakeGenerator()
        # Live voice off: the suite must never open a billable session.
        self.settings = MeetingSettings(live_enabled=False, live_model="")

        app = FastAPI()
        app.include_router(meeting_routes.router)
        app.dependency_overrides[meeting_routes.get_workflow_engine] = lambda: self.workflows
        app.dependency_overrides[meeting_routes.get_artifact_store] = lambda: self.artifacts
        app.dependency_overrides[meeting_routes.get_meeting_store] = lambda: self.meetings
        app.dependency_overrides[meeting_routes.get_transcript_store] = lambda: self.transcripts
        app.dependency_overrides[meeting_routes.get_settings] = lambda: self.settings
        app.dependency_overrides[meeting_routes.get_structured_generator] = lambda: self.generator
        self.client = TestClient(app)

    def new_workflow(self, *, advance_to_discovery: bool = True) -> str:
        workflow = self.workflows.create(
            WorkflowCreateRequest(
                name="Maintenance Portal",
                client_request="We manage rental properties and need a maintenance portal.",
                client_name="Alpha Property Group",
            )
        )
        if advance_to_discovery:
            self.workflows.transition(
                workflow.workflow_id,
                TransitionRequest(
                    action="start_discovery",
                    actor=ActorRole.MANAGER,
                    idempotency_key="start-discovery-1",
                ),
            )
        return workflow.workflow_id

    def open_meeting(self, workflow_id: str) -> str:
        response = self.client.post(
            f"/v1/workflows/{workflow_id}/meetings", json={"participant_name": "Dana"}
        )
        assert response.status_code == 201, response.text
        return response.json()["session"]["meeting_id"]

    def consent(self, meeting_id: str) -> None:
        response = self.client.post(
            f"/v1/meetings/{meeting_id}/consent",
            json={
                "granted": True,
                "participant_name": "Dana",
                "ai_disclosure_acknowledged": True,
                "transcription_acknowledged": True,
            },
        )
        assert response.status_code == 200, response.text


@pytest.fixture()
def harness() -> Harness:
    return Harness()


# ------------------------------------------------------------ capability -- #


def test_capabilities_report_fallback_when_live_is_not_configured(harness: Harness) -> None:
    body = harness.client.get("/v1/meetings/capabilities").json()
    assert body["live_voice_available"] is False
    assert body["mode"] == "fallback_text"
    assert "GEMINI_LIVE_ENABLED" in body["reason"]


def test_capabilities_do_not_claim_third_party_conferencing(harness: Harness) -> None:
    body = harness.client.get("/v1/meetings/capabilities").json()
    assert "does not join Google Meet" in body["note"]


def test_boundaries_endpoint_denies_every_forbidden_capability(harness: Harness) -> None:
    report = harness.client.get("/v1/meetings/boundaries").json()
    assert report and all(entry["allowed"] is False for entry in report)


# --------------------------------------------------------------- consent -- #


def test_meeting_starts_without_consent(harness: Harness) -> None:
    workflow_id = harness.new_workflow()
    meeting_id = harness.open_meeting(workflow_id)
    session = harness.client.get(f"/v1/meetings/{meeting_id}").json()["session"]
    assert session["state"] == "CREATED"
    assert session["consent"] is None


def test_utterances_are_refused_without_consent(harness: Harness) -> None:
    workflow_id = harness.new_workflow()
    meeting_id = harness.open_meeting(workflow_id)

    response = harness.client.post(
        f"/v1/meetings/{meeting_id}/utterances",
        json={"speaker": "client", "content": "We need a portal."},
    )
    assert response.status_code == 403
    assert "consent" in response.json()["detail"].lower()


def test_declined_consent_is_rejected(harness: Harness) -> None:
    workflow_id = harness.new_workflow()
    meeting_id = harness.open_meeting(workflow_id)
    response = harness.client.post(
        f"/v1/meetings/{meeting_id}/consent",
        json={
            "granted": False,
            "participant_name": "Dana",
            "ai_disclosure_acknowledged": True,
            "transcription_acknowledged": True,
        },
    )
    assert response.status_code == 403


def test_partial_acknowledgement_is_rejected(harness: Harness) -> None:
    """Both the AI disclosure and the transcription notice must be acknowledged."""
    workflow_id = harness.new_workflow()
    meeting_id = harness.open_meeting(workflow_id)
    response = harness.client.post(
        f"/v1/meetings/{meeting_id}/consent",
        json={
            "granted": True,
            "participant_name": "Dana",
            "ai_disclosure_acknowledged": True,
            "transcription_acknowledged": False,
        },
    )
    assert response.status_code == 403


def test_websocket_refuses_without_consent(harness: Harness) -> None:
    workflow_id = harness.new_workflow()
    meeting_id = harness.open_meeting(workflow_id)

    with harness.client.websocket_connect(f"/v1/meetings/{meeting_id}/live") as socket:
        frame = socket.receive_json()
        assert frame["type"] == "error"
        assert frame["code"] == "consent_required"


def test_finalize_refuses_without_consent(harness: Harness) -> None:
    workflow_id = harness.new_workflow()
    meeting_id = harness.open_meeting(workflow_id)
    response = harness.client.post(f"/v1/meetings/{meeting_id}/finalize")
    assert response.status_code == 403
    assert harness.generator.calls == 0


# ------------------------------------------------------------ transcript -- #


def test_transcript_orders_and_dedupes_across_reconnects(harness: Harness) -> None:
    workflow_id = harness.new_workflow()
    meeting_id = harness.open_meeting(workflow_id)
    harness.consent(meeting_id)

    for index, text in enumerate(["First point.", "Second point."], start=1):
        response = harness.client.post(
            f"/v1/meetings/{meeting_id}/utterances",
            json={"speaker": "client", "content": text, "dedupe_key": f"turn-{index}"},
        )
        assert response.status_code == 201

    # Reconnecting client replays turn-2; it must not create a third utterance.
    replay = harness.client.post(
        f"/v1/meetings/{meeting_id}/utterances",
        json={"speaker": "client", "content": "Second point.", "dedupe_key": "turn-2"},
    )
    assert replay.status_code == 201

    body = harness.client.get(f"/v1/meetings/{meeting_id}/transcript").json()
    assert [item["sequence_number"] for item in body["utterances"]] == [1, 2]


def test_websocket_records_text_in_fallback_mode(harness: Harness) -> None:
    workflow_id = harness.new_workflow()
    meeting_id = harness.open_meeting(workflow_id)
    harness.consent(meeting_id)

    with harness.client.websocket_connect(f"/v1/meetings/{meeting_id}/live") as socket:
        ready = socket.receive_json()
        assert ready["type"] == "ready"
        assert ready["mode"] == "fallback_text"

        socket.send_json({"type": "text", "content": "We manage rental properties."})
        frame = socket.receive_json()
        assert frame["type"] == "utterance"
        # Fallback text must never be labelled as live voice.
        assert frame["utterance"]["source"] == "written_brief"
        socket.send_json({"type": "end"})


def test_websocket_refuses_audio_in_fallback_mode(harness: Harness) -> None:
    workflow_id = harness.new_workflow()
    meeting_id = harness.open_meeting(workflow_id)
    harness.consent(meeting_id)

    with harness.client.websocket_connect(f"/v1/meetings/{meeting_id}/live") as socket:
        socket.receive_json()
        socket.send_json({"type": "audio", "data": "AAAA"})
        frame = socket.receive_json()
        assert frame["type"] == "error"
        assert frame["code"] == "fallback_mode"


def test_websocket_reconnect_is_counted(harness: Harness) -> None:
    workflow_id = harness.new_workflow()
    meeting_id = harness.open_meeting(workflow_id)
    harness.consent(meeting_id)

    with harness.client.websocket_connect(f"/v1/meetings/{meeting_id}/live") as socket:
        assert socket.receive_json()["reconnect_count"] == 0
        socket.send_json({"type": "end"})

    with harness.client.websocket_connect(f"/v1/meetings/{meeting_id}/live") as socket:
        assert socket.receive_json()["reconnect_count"] == 1
        socket.send_json({"type": "end"})


# --------------------------------------------------------------- handoff -- #


def test_finalize_produces_three_linked_artifacts_and_stops_for_approval(
    harness: Harness,
) -> None:
    workflow_id = harness.new_workflow()
    meeting_id = harness.open_meeting(workflow_id)
    harness.consent(meeting_id)
    harness.client.post(
        f"/v1/meetings/{meeting_id}/utterances",
        json={"speaker": "client", "content": "We manage rental properties."},
    )

    response = harness.client.post(f"/v1/meetings/{meeting_id}/finalize")
    assert response.status_code == 200, response.text
    handoff = response.json()

    assert handoff["workflow_state"] == "SPEC_REVIEW"
    assert handoff["awaiting"] == "human_specification_approval"
    assert handoff["requested_transition"] == "submit_specification"
    assert handoff["validation_problems"] == []

    stored = {item.logical_name: item for item in harness.artifacts.list(workflow_id)}
    assert set(stored) == {"MEETING_TRANSCRIPT", "DISCOVERY_RECORD", "SPECIFICATIONS"}

    # Lineage: record cites the transcript, specification cites both.
    assert stored["DISCOVERY_RECORD"].source_artifact_ids == [
        stored["MEETING_TRANSCRIPT"].artifact_id
    ]
    assert stored["SPECIFICATIONS"].source_artifact_ids == [
        stored["MEETING_TRANSCRIPT"].artifact_id,
        stored["DISCOVERY_RECORD"].artifact_id,
    ]

    # Nothing is approved by the agent.
    assert all(not item.approved for item in stored.values())
    assert all(item.generated_by is ActorRole.DISCOVERY for item in stored.values())


def test_finalize_runs_generation_separately_from_the_conversation(
    harness: Harness,
) -> None:
    """Two deliberate calls: the discovery record, then the specification."""
    workflow_id = harness.new_workflow()
    meeting_id = harness.open_meeting(workflow_id)
    harness.consent(meeting_id)
    harness.client.post(
        f"/v1/meetings/{meeting_id}/utterances",
        json={"speaker": "client", "content": "We manage rental properties."},
    )
    harness.client.post(f"/v1/meetings/{meeting_id}/finalize")
    assert harness.generator.calls == 2


def test_transcript_is_frozen_after_finalize(harness: Harness) -> None:
    workflow_id = harness.new_workflow()
    meeting_id = harness.open_meeting(workflow_id)
    harness.consent(meeting_id)
    harness.client.post(
        f"/v1/meetings/{meeting_id}/utterances",
        json={"speaker": "client", "content": "Initial point."},
    )
    harness.client.post(f"/v1/meetings/{meeting_id}/finalize")

    late = harness.client.post(
        f"/v1/meetings/{meeting_id}/utterances",
        json={"speaker": "client", "content": "A late addition."},
    )
    assert late.status_code == 409


def test_finalize_requires_the_discovery_state(harness: Harness) -> None:
    workflow_id = harness.new_workflow(advance_to_discovery=False)
    meeting_id = harness.open_meeting(workflow_id)
    harness.consent(meeting_id)

    response = harness.client.post(f"/v1/meetings/{meeting_id}/finalize")
    assert response.status_code == 409
    assert "DISCOVERY" in response.json()["detail"]
    assert harness.generator.calls == 0


def test_meeting_for_an_unknown_workflow_is_rejected(harness: Harness) -> None:
    response = harness.client.post(
        "/v1/workflows/does-not-exist/meetings", json={"participant_name": "Dana"}
    )
    assert response.status_code == 404


def test_unknown_meeting_websocket_is_closed(harness: Harness) -> None:
    with harness.client.websocket_connect("/v1/meetings/nope/live") as socket:
        frame = socket.receive_json()
        assert frame["type"] == "error"
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()

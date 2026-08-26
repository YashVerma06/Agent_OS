import pytest

from app.contracts import (
    ActorRole,
    AgentRunStatus,
    HandoffEnvelope,
    HandoffGate,
    WorkflowCreateRequest,
)
from app.orchestration.handoff import HandoffDenied, validate_handoff
from app.platform.workflow import InMemoryWorkflowEngine


def _snapshot(state_action: str, actor: ActorRole):
    from app.contracts import TransitionRequest

    workflows = InMemoryWorkflowEngine()
    workflow = workflows.create(
        WorkflowCreateRequest(
            name="Handoff test",
            client_request="Build a controlled handoff test application.",
        )
    )
    workflows.transition(
        workflow.workflow_id,
        TransitionRequest(
            action=state_action,
            actor=actor,
            idempotency_key=f"handoff-{state_action}",
        ),
    )
    return workflows.get(workflow.workflow_id)


def test_discovery_cannot_request_planner_before_human_gate() -> None:
    snapshot = _snapshot("start_discovery", ActorRole.MANAGER)
    envelope = HandoffEnvelope(
        workflow_id=snapshot.workflow_id,
        from_agent=ActorRole.DISCOVERY,
        requested_next_agent=ActorRole.PLANNER,
        required_gate=HandoffGate.NONE,
        status=AgentRunStatus.COMPLETED,
        idempotency_key="handoff-discovery-invalid",
    )

    with pytest.raises(HandoffDenied, match="specification approval"):
        validate_handoff(snapshot, envelope)


def test_discovery_may_stop_at_specification_approval() -> None:
    snapshot = _snapshot("start_discovery", ActorRole.MANAGER)
    envelope = HandoffEnvelope(
        workflow_id=snapshot.workflow_id,
        from_agent=ActorRole.DISCOVERY,
        required_gate=HandoffGate.SPECIFICATION_APPROVAL,
        status=AgentRunStatus.WAITING_FOR_HUMAN,
        idempotency_key="handoff-discovery-valid",
    )

    validate_handoff(snapshot, envelope)

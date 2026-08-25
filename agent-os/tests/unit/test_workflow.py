from uuid import uuid4

import pytest

from app.contracts import (
    ActorRole,
    TransitionRequest,
    WorkflowCreateRequest,
    WorkflowState,
)
from app.platform.workflow import InMemoryWorkflowEngine, TransitionDenied


def request(action: str, actor: ActorRole, key: str | None = None) -> TransitionRequest:
    return TransitionRequest(
        action=action,
        actor=actor,
        idempotency_key=key or f"test-{uuid4()}",
    )


def create_workflow(engine: InMemoryWorkflowEngine) -> str:
    workflow = engine.create(
        WorkflowCreateRequest(
            name="Maintenance portal",
            client_request="Build a maintenance request portal for tenants and property managers.",
        )
    )
    return workflow.workflow_id


def test_golden_path_includes_failure_repair_and_human_gates() -> None:
    engine = InMemoryWorkflowEngine()
    workflow_id = create_workflow(engine)

    steps = [
        ("start_discovery", ActorRole.MANAGER, WorkflowState.DISCOVERY),
        ("submit_specification", ActorRole.DISCOVERY, WorkflowState.SPEC_REVIEW),
        ("approve_specification", ActorRole.HUMAN, WorkflowState.PLANNING),
        ("submit_plan", ActorRole.PLANNER, WorkflowState.IMPLEMENTING),
        ("submit_build", ActorRole.BUILDER, WorkflowState.REVIEWING),
        ("request_revision", ActorRole.REVIEWER, WorkflowState.REVISION_REQUIRED),
        ("submit_revision", ActorRole.BUILDER, WorkflowState.REVIEWING),
        ("pass_review", ActorRole.REVIEWER, WorkflowState.RELEASE_REVIEW),
        ("approve_release", ActorRole.HUMAN, WorkflowState.RELEASE_APPROVED),
        ("release_staging", ActorRole.RELEASE_SERVICE, WorkflowState.STAGING_RELEASED),
    ]

    for action, actor, expected_state in steps:
        result = engine.transition(workflow_id, request(action, actor))
        assert result.workflow.state == expected_state
        assert result.audit_event.allowed is True

    final = engine.get(workflow_id)
    assert final.reviewer_passed is True
    assert final.release_approved is True
    assert len(engine.audit(workflow_id)) == len(steps)


def test_builder_is_denied_before_specification_approval_and_denial_is_audited() -> None:
    engine = InMemoryWorkflowEngine()
    workflow_id = create_workflow(engine)
    engine.transition(workflow_id, request("start_discovery", ActorRole.MANAGER))
    engine.transition(workflow_id, request("submit_specification", ActorRole.DISCOVERY))

    with pytest.raises(TransitionDenied) as exc_info:
        engine.transition(workflow_id, request("submit_plan", ActorRole.BUILDER))

    assert exc_info.value.audit_event.allowed is False
    assert exc_info.value.audit_event.state_before == WorkflowState.SPEC_REVIEW
    assert engine.audit(workflow_id)[-1].rule_id == "workflow.invalid_transition"


def test_idempotent_transition_replays_without_incrementing_version() -> None:
    engine = InMemoryWorkflowEngine()
    workflow_id = create_workflow(engine)
    transition = request("start_discovery", ActorRole.MANAGER, "start-discovery-once")

    first = engine.transition(workflow_id, transition)
    second = engine.transition(workflow_id, transition)

    assert first.replayed is False
    assert second.replayed is True
    assert second.workflow.version == first.workflow.version
    assert len(engine.audit(workflow_id)) == 1

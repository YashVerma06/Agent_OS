from __future__ import annotations

from app.contracts import (
    ActorRole,
    AgentRunStatus,
    HandoffEnvelope,
    HandoffGate,
    WorkflowSnapshot,
    WorkflowState,
)


class HandoffDenied(ValueError):
    pass


SPECIALIST_BY_STATE: dict[WorkflowState, ActorRole] = {
    WorkflowState.INTAKE: ActorRole.DISCOVERY,
    WorkflowState.DISCOVERY: ActorRole.DISCOVERY,
    WorkflowState.PLANNING: ActorRole.PLANNER,
    WorkflowState.IMPLEMENTING: ActorRole.BUILDER,
    WorkflowState.REVIEWING: ActorRole.REVIEWER,
    WorkflowState.REVISION_REQUIRED: ActorRole.BUILDER,
}

GATE_BY_STATE: dict[WorkflowState, HandoffGate] = {
    WorkflowState.SPEC_REVIEW: HandoffGate.SPECIFICATION_APPROVAL,
    WorkflowState.RELEASE_REVIEW: HandoffGate.RELEASE_APPROVAL,
}

TERMINAL_STATES = frozenset({WorkflowState.STAGING_RELEASED, WorkflowState.REJECTED})


def specialist_for_state(state: WorkflowState) -> ActorRole | None:
    return SPECIALIST_BY_STATE.get(state)


def gate_for_state(state: WorkflowState) -> HandoffGate:
    return GATE_BY_STATE.get(state, HandoffGate.NONE)


def validate_delegation(snapshot: WorkflowSnapshot, target_agent: ActorRole) -> None:
    gate = gate_for_state(snapshot.state)
    if gate != HandoffGate.NONE:
        raise HandoffDenied(f"Workflow is waiting at the {gate.value} human gate.")
    expected = specialist_for_state(snapshot.state)
    if expected is None:
        raise HandoffDenied(
            f"Workflow state {snapshot.state.value} has no LLM specialist delegation."
        )
    if target_agent != expected:
        raise HandoffDenied(
            f"Workflow state {snapshot.state.value} delegates only to {expected.value}."
        )


def validate_handoff(snapshot: WorkflowSnapshot, envelope: HandoffEnvelope) -> None:
    if envelope.workflow_id != snapshot.workflow_id:
        raise HandoffDenied("Handoff belongs to a different workflow.")

    validate_delegation(snapshot, envelope.from_agent)

    if snapshot.state == WorkflowState.DISCOVERY:
        if envelope.required_gate != HandoffGate.SPECIFICATION_APPROVAL:
            raise HandoffDenied("Discovery completion must request specification approval.")
        if envelope.status != AgentRunStatus.WAITING_FOR_HUMAN:
            raise HandoffDenied("Discovery must stop while waiting for human approval.")
        if envelope.requested_next_agent is not None:
            raise HandoffDenied("Discovery cannot bypass the specification approval gate.")
        return

    if snapshot.state == WorkflowState.PLANNING:
        expected_next = ActorRole.BUILDER
    elif snapshot.state in {WorkflowState.IMPLEMENTING, WorkflowState.REVISION_REQUIRED}:
        expected_next = ActorRole.REVIEWER
    elif snapshot.state == WorkflowState.REVIEWING:
        if envelope.requested_next_agent == ActorRole.BUILDER:
            if envelope.required_gate != HandoffGate.NONE:
                raise HandoffDenied("A revision handoff cannot request a release gate.")
            return
        if envelope.requested_next_agent is None:
            if envelope.required_gate != HandoffGate.RELEASE_APPROVAL:
                raise HandoffDenied("A passing review must request human release approval.")
            if envelope.status != AgentRunStatus.WAITING_FOR_HUMAN:
                raise HandoffDenied("A passing review must stop at the human release gate.")
            return
        raise HandoffDenied("Reviewer may request Builder revision or human release approval.")
    else:
        raise HandoffDenied(
            f"State {snapshot.state.value} does not accept a specialist completion handoff."
        )

    if envelope.requested_next_agent != expected_next:
        raise HandoffDenied(f"The only legal requested next agent is {expected_next.value}.")
    if envelope.required_gate != HandoffGate.NONE:
        raise HandoffDenied("This specialist handoff does not have a human gate.")
    if envelope.status != AgentRunStatus.COMPLETED:
        raise HandoffDenied("A specialist-to-specialist handoff must be completed.")

from __future__ import annotations

from app.contracts import (
    ActorRole,
    AgentRunRequest,
    AgentRunResult,
    AgentRunStatus,
    HandoffGate,
    NextActionRequest,
    OrchestrationDecision,
    WorkflowState,
)
from app.orchestration.context import ContextAssembler
from app.orchestration.handoff import (
    TERMINAL_STATES,
    gate_for_state,
    specialist_for_state,
    validate_handoff,
)
from app.platform.artifacts import ArtifactError, InMemoryArtifactStore
from app.platform.workflow import InMemoryWorkflowEngine


class OrchestrationError(ValueError):
    pass


class OrchestrationIdempotencyConflict(OrchestrationError):
    pass


class OrchestrationCoordinator:
    """Prepare and validate agent work without allowing model-driven state mutation."""

    def __init__(
        self,
        *,
        workflows: InMemoryWorkflowEngine,
        artifacts: InMemoryArtifactStore,
        contexts: ContextAssembler,
    ) -> None:
        self._workflows = workflows
        self._artifacts = artifacts
        self._contexts = contexts
        self._decisions: dict[
            tuple[str, str], tuple[tuple[int, WorkflowState], OrchestrationDecision]
        ] = {}

    def prepare_next(
        self, workflow_id: str, request: NextActionRequest
    ) -> OrchestrationDecision:
        snapshot = self._workflows.get(workflow_id)
        slot = (workflow_id, request.idempotency_key)
        signature = (snapshot.version, snapshot.state)
        existing = self._decisions.get(slot)
        if existing is not None:
            existing_signature, decision = existing
            if existing_signature != signature:
                raise OrchestrationIdempotencyConflict(
                    "The idempotency key was reused after the workflow state changed."
                )
            return decision.model_copy(update={"replayed": True}, deep=True)

        gate = gate_for_state(snapshot.state)
        if gate != HandoffGate.NONE:
            decision = OrchestrationDecision(
                workflow_id=workflow_id,
                workflow_state=snapshot.state,
                status=AgentRunStatus.WAITING_FOR_HUMAN,
                required_gate=gate,
                reason=f"Workflow is waiting for {gate.value}.",
                trace_id=request.trace_id,
            )
        elif snapshot.state == WorkflowState.INTAKE:
            decision = OrchestrationDecision(
                workflow_id=workflow_id,
                workflow_state=snapshot.state,
                status=AgentRunStatus.READY,
                target_agent=ActorRole.MANAGER,
                reason=(
                    "The Manager must authorize start_discovery before the Discovery "
                    "specialist is invoked."
                ),
                trace_id=request.trace_id,
            )
        elif snapshot.state == WorkflowState.RELEASE_APPROVED:
            decision = OrchestrationDecision(
                workflow_id=workflow_id,
                workflow_state=snapshot.state,
                status=AgentRunStatus.READY,
                target_agent=ActorRole.RELEASE_SERVICE,
                reason="The deterministic Release Service is the next executor.",
                trace_id=request.trace_id,
            )
        elif snapshot.state in TERMINAL_STATES:
            decision = OrchestrationDecision(
                workflow_id=workflow_id,
                workflow_state=snapshot.state,
                status=AgentRunStatus.COMPLETED,
                reason="Workflow is terminal and has no next executor.",
                trace_id=request.trace_id,
            )
        else:
            target = specialist_for_state(snapshot.state)
            if target is None:
                raise OrchestrationError(
                    f"No orchestration route exists for {snapshot.state.value}."
                )
            context = self._contexts.build(
                workflow_id, target, trace_id=request.trace_id
            )
            run_request = AgentRunRequest(
                workflow_id=workflow_id,
                target_agent=target,
                context=context,
                input_artifact_ids=[
                    artifact.artifact_id for artifact in context.artifact_references
                ],
                trace_id=request.trace_id,
                idempotency_key=request.idempotency_key,
            )
            decision = OrchestrationDecision(
                workflow_id=workflow_id,
                workflow_state=snapshot.state,
                status=AgentRunStatus.READY,
                target_agent=target,
                reason=(
                    "Deterministic workflow routing prepared a scoped specialist request."
                ),
                run_request=run_request,
                trace_id=request.trace_id,
            )

        self._decisions[slot] = (signature, decision)
        return decision.model_copy(deep=True)

    def validate_result(self, result: AgentRunResult) -> AgentRunResult:
        snapshot = self._workflows.get(result.workflow_id)
        expected = specialist_for_state(snapshot.state)
        if expected != result.agent:
            raise OrchestrationError(
                "Agent result does not match the specialist assigned to the workflow state."
            )
        for artifact_id in result.output_artifact_ids:
            try:
                self._artifacts.get(result.workflow_id, artifact_id)
            except ArtifactError as exc:
                raise OrchestrationError(
                    "Agent result references an artifact outside this workflow."
                ) from exc
        if result.handoff is not None:
            validate_handoff(snapshot, result.handoff)
            if result.handoff.trace_id != result.trace_id:
                raise OrchestrationError(
                    "Handoff and agent result must share the same trace ID."
                )
            if set(result.handoff.output_artifact_ids) != set(result.output_artifact_ids):
                raise OrchestrationError(
                    "Handoff artifact references must match the agent run result."
                )
            if len(set(result.output_artifact_ids)) != len(result.output_artifact_ids):
                raise OrchestrationError("Agent result contains duplicate artifact references.")
        return result.model_copy(deep=True)

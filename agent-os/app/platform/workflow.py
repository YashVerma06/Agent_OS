from __future__ import annotations

from dataclasses import dataclass
from typing import Final
from uuid import uuid4

from app.contracts import (
    ActorRole,
    AuditEvent,
    TransitionRequest,
    TransitionResult,
    WorkflowCreateRequest,
    WorkflowSnapshot,
    WorkflowState,
    utc_now,
)


class WorkflowNotFound(KeyError):
    pass


class TransitionDenied(ValueError):
    def __init__(self, message: str, audit_event: AuditEvent) -> None:
        super().__init__(message)
        self.audit_event = audit_event


class IdempotencyConflict(ValueError):
    pass


@dataclass(frozen=True)
class TransitionRule:
    next_state: WorkflowState
    allowed_actors: frozenset[ActorRole]
    rule_id: str


TRANSITIONS: Final[dict[tuple[WorkflowState, str], TransitionRule]] = {
    (WorkflowState.INTAKE, "start_discovery"): TransitionRule(
        WorkflowState.DISCOVERY, frozenset({ActorRole.MANAGER}), "workflow.start_discovery"
    ),
    (WorkflowState.DISCOVERY, "submit_specification"): TransitionRule(
        WorkflowState.SPEC_REVIEW,
        frozenset({ActorRole.DISCOVERY}),
        "workflow.submit_specification",
    ),
    (WorkflowState.SPEC_REVIEW, "approve_specification"): TransitionRule(
        WorkflowState.PLANNING, frozenset({ActorRole.HUMAN}), "gate.specification_approval"
    ),
    (WorkflowState.SPEC_REVIEW, "reject_specification"): TransitionRule(
        WorkflowState.DISCOVERY, frozenset({ActorRole.HUMAN}), "gate.specification_rejection"
    ),
    (WorkflowState.PLANNING, "submit_plan"): TransitionRule(
        WorkflowState.IMPLEMENTING, frozenset({ActorRole.PLANNER}), "workflow.submit_plan"
    ),
    (WorkflowState.IMPLEMENTING, "submit_build"): TransitionRule(
        WorkflowState.REVIEWING, frozenset({ActorRole.BUILDER}), "workflow.submit_build"
    ),
    (WorkflowState.REVIEWING, "request_revision"): TransitionRule(
        WorkflowState.REVISION_REQUIRED,
        frozenset({ActorRole.REVIEWER}),
        "workflow.request_revision",
    ),
    (WorkflowState.REVISION_REQUIRED, "submit_revision"): TransitionRule(
        WorkflowState.REVIEWING, frozenset({ActorRole.BUILDER}), "workflow.submit_revision"
    ),
    (WorkflowState.REVIEWING, "pass_review"): TransitionRule(
        WorkflowState.RELEASE_REVIEW, frozenset({ActorRole.REVIEWER}), "workflow.pass_review"
    ),
    (WorkflowState.RELEASE_REVIEW, "approve_release"): TransitionRule(
        WorkflowState.RELEASE_APPROVED,
        frozenset({ActorRole.HUMAN}),
        "gate.release_approval",
    ),
    (WorkflowState.RELEASE_REVIEW, "reject_release"): TransitionRule(
        WorkflowState.REVIEWING, frozenset({ActorRole.HUMAN}), "gate.release_rejection"
    ),
    (WorkflowState.RELEASE_APPROVED, "release_staging"): TransitionRule(
        WorkflowState.STAGING_RELEASED,
        frozenset({ActorRole.RELEASE_SERVICE}),
        "workflow.release_staging",
    ),
}


class InMemoryWorkflowEngine:
    """Reference state machine. Persistence adapters must preserve these semantics."""

    def __init__(self) -> None:
        self._workflows: dict[str, WorkflowSnapshot] = {}
        self._audit: dict[str, list[AuditEvent]] = {}
        self._create_idempotency: dict[
            tuple[str, str], tuple[tuple[object, ...], WorkflowSnapshot]
        ] = {}
        self._idempotency: dict[
            tuple[str, str], tuple[tuple[str, ActorRole], TransitionResult]
        ] = {}

    def create(self, request: WorkflowCreateRequest) -> WorkflowSnapshot:
        signature = (
            request.name,
            request.client_request,
            request.organization_id,
            request.workforce_id,
            request.client_name,
            request.client_contact_name,
            request.client_contact_email,
        )
        idempotency_slot = (request.tenant_id, request.idempotency_key)
        existing = self._create_idempotency.get(idempotency_slot)
        if existing is not None:
            existing_signature, snapshot = existing
            if existing_signature != signature:
                raise IdempotencyConflict(
                    "The idempotency key was already used for a different workflow request."
                )
            return snapshot.model_copy(deep=True)

        workflow_id = str(uuid4())
        snapshot = WorkflowSnapshot(
            workflow_id=workflow_id,
            **request.model_dump(exclude={"idempotency_key"}),
        )
        self._workflows[workflow_id] = snapshot
        self._audit[workflow_id] = []
        self._create_idempotency[idempotency_slot] = (signature, snapshot)
        return snapshot.model_copy(deep=True)

    def get(self, workflow_id: str) -> WorkflowSnapshot:
        snapshot = self._workflows.get(workflow_id)
        if snapshot is None:
            raise WorkflowNotFound(workflow_id)
        return snapshot.model_copy(deep=True)

    def audit(self, workflow_id: str) -> list[AuditEvent]:
        if workflow_id not in self._workflows:
            raise WorkflowNotFound(workflow_id)
        return [event.model_copy(deep=True) for event in self._audit[workflow_id]]

    def record_denial(
        self,
        workflow_id: str,
        request: TransitionRequest,
        *,
        reason: str,
        rule_id: str,
    ) -> AuditEvent:
        """Record a denial detected by a deterministic service before transition lookup."""

        snapshot = self._workflows.get(workflow_id)
        if snapshot is None:
            raise WorkflowNotFound(workflow_id)
        return self._denial(snapshot, request, reason, rule_id)

    def transition(self, workflow_id: str, request: TransitionRequest) -> TransitionResult:
        snapshot = self._workflows.get(workflow_id)
        if snapshot is None:
            raise WorkflowNotFound(workflow_id)

        idempotency_slot = (workflow_id, request.idempotency_key)
        signature = (request.action, request.actor)
        existing = self._idempotency.get(idempotency_slot)
        if existing is not None:
            existing_signature, existing_result = existing
            if existing_signature != signature:
                raise IdempotencyConflict(
                    "The idempotency key was already used for a different action or actor."
                )
            return existing_result.model_copy(update={"replayed": True}, deep=True)

        rule = TRANSITIONS.get((snapshot.state, request.action))
        if rule is None:
            audit = self._denial(
                snapshot,
                request,
                "No transition exists for this action in the current workflow state.",
                "workflow.invalid_transition",
            )
            raise TransitionDenied(audit.reason, audit)

        if request.actor not in rule.allowed_actors:
            audit = self._denial(
                snapshot,
                request,
                "The actor role is not authorized to execute this workflow transition.",
                "workflow.actor_denied",
            )
            raise TransitionDenied(audit.reason, audit)

        updates: dict[str, object] = {
            "state": rule.next_state,
            "version": snapshot.version + 1,
            "updated_at": utc_now(),
        }
        if request.action == "request_revision":
            updates["reviewer_passed"] = False
        elif request.action == "pass_review":
            updates["reviewer_passed"] = True
        elif request.action == "approve_release":
            if not snapshot.reviewer_passed:
                audit = self._denial(
                    snapshot,
                    request,
                    (
                        "Release approval is impossible until the Reviewer has passed "
                        "the current build."
                    ),
                    "gate.review_evidence_missing",
                )
                raise TransitionDenied(audit.reason, audit)
            updates["release_approved"] = True

        updated = snapshot.model_copy(update=updates, deep=True)
        self._workflows[workflow_id] = updated
        audit = AuditEvent(
            workflow_id=workflow_id,
            actor=request.actor,
            action=request.action,
            state_before=snapshot.state,
            state_after=updated.state,
            allowed=True,
            reason="Transition allowed by the deterministic workflow rule.",
            rule_id=rule.rule_id,
            idempotency_key=request.idempotency_key,
            trace_id=request.trace_id,
            metadata=request.metadata,
        )
        self._audit[workflow_id].append(audit)
        result = TransitionResult(workflow=updated, audit_event=audit)
        self._idempotency[idempotency_slot] = (signature, result)
        return result.model_copy(deep=True)

    def _denial(
        self,
        snapshot: WorkflowSnapshot,
        request: TransitionRequest,
        reason: str,
        rule_id: str,
    ) -> AuditEvent:
        audit = AuditEvent(
            workflow_id=snapshot.workflow_id,
            actor=request.actor,
            action=request.action,
            state_before=snapshot.state,
            state_after=snapshot.state,
            allowed=False,
            reason=reason,
            rule_id=rule_id,
            idempotency_key=request.idempotency_key,
            trace_id=request.trace_id,
            metadata=request.metadata,
        )
        self._audit[snapshot.workflow_id].append(audit)
        return audit

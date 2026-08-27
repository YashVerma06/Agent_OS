from __future__ import annotations

from app.contracts import (
    ActorRole,
    Capability,
    PolicyDecision,
    PolicyEvaluationRequest,
    WorkflowState,
)

BASE_ALLOW: dict[ActorRole, frozenset[Capability]] = {
    ActorRole.MANAGER: frozenset(
        {Capability.WORKFLOW_INSPECT, Capability.AGENT_DELEGATE, Capability.CALENDAR_EVENT_CREATE}
    ),
    ActorRole.DISCOVERY: frozenset(
        {Capability.WORKFLOW_INSPECT, Capability.ARTIFACT_SPECIFICATION_WRITE}
    ),
    ActorRole.PLANNER: frozenset({Capability.WORKFLOW_INSPECT, Capability.ARTIFACT_PLAN_WRITE}),
    ActorRole.BUILDER: frozenset(
        {
            Capability.WORKFLOW_INSPECT,
            Capability.REPOSITORY_READ,
            Capability.REPOSITORY_WRITE,
            Capability.TEST_RUN,
        }
    ),
    ActorRole.REVIEWER: frozenset(
        {
            Capability.WORKFLOW_INSPECT,
            Capability.REPOSITORY_READ,
            Capability.TEST_RUN,
            Capability.SECURITY_SCAN,
        }
    ),
    ActorRole.RELEASE_SERVICE: frozenset(
        {Capability.WORKFLOW_INSPECT, Capability.DEPLOYMENT_STAGING}
    ),
    ActorRole.HUMAN: frozenset({Capability.WORKFLOW_INSPECT, Capability.APPROVAL_DECIDE}),
}


def candidate_capabilities_for(actor: ActorRole) -> list[Capability]:
    """Return role-level candidates; contextual policy evaluation is still mandatory."""

    return sorted(BASE_ALLOW.get(actor, frozenset()), key=lambda capability: capability.value)


class PolicyEngine:
    """Deny-by-default authorization independent of all agent prompts."""

    def evaluate(self, request: PolicyEvaluationRequest) -> PolicyDecision:
        common = {
            "actor": request.actor,
            "capability": request.capability,
            "workflow_state": request.workflow_state,
            "resource": request.resource,
            "trace_id": request.trace_id,
        }

        if request.capability in {
            Capability.DEPLOYMENT_PRODUCTION,
            Capability.SECRET_READ,
            Capability.PROTECTED_BRANCH_WRITE,
        }:
            return PolicyDecision(
                allowed=False,
                reason="Capability is globally disabled for the hackathon MVP.",
                rule_id="global.explicit_deny",
                **common,
            )

        if request.capability not in BASE_ALLOW.get(request.actor, frozenset()):
            return PolicyDecision(
                allowed=False,
                reason="The actor role has no allow rule for this capability.",
                rule_id="role.default_deny",
                **common,
            )

        if request.capability == Capability.CALENDAR_EVENT_CREATE:
            if not request.approval_present:
                return PolicyDecision(
                    allowed=False,
                    reason="Calendar creation requires an authenticated human approval record.",
                    rule_id="calendar.human_gate",
                    **common,
                )

        if request.capability == Capability.REPOSITORY_WRITE:
            if request.workflow_state not in {
                WorkflowState.IMPLEMENTING,
                WorkflowState.REVISION_REQUIRED,
            }:
                return PolicyDecision(
                    allowed=False,
                    reason="Repository writes are allowed only while implementing or repairing.",
                    rule_id="repository.workflow_state",
                    **common,
                )
            if not request.resource or not request.resource.startswith("agentos/"):
                return PolicyDecision(
                    allowed=False,
                    reason="Builder writes require an allowlisted agentos/ branch resource.",
                    rule_id="repository.branch_jail",
                    **common,
                )

        if request.capability == Capability.DEPLOYMENT_STAGING:
            if request.workflow_state != WorkflowState.RELEASE_APPROVED:
                return PolicyDecision(
                    allowed=False,
                    reason="Staging deployment requires the RELEASE_APPROVED workflow state.",
                    rule_id="deployment.workflow_state",
                    **common,
                )
            if not request.approval_present:
                return PolicyDecision(
                    allowed=False,
                    reason="Staging deployment requires a verified release approval record.",
                    rule_id="deployment.human_gate",
                    **common,
                )

        return PolicyDecision(
            allowed=True,
            reason="Explicit role and contextual policy rules allow the capability.",
            rule_id="role.explicit_allow",
            **common,
        )

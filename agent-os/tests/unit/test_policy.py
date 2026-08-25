from app.contracts import (
    ActorRole,
    Capability,
    PolicyEvaluationRequest,
    WorkflowState,
)
from app.platform.policy import PolicyEngine


def test_discovery_cannot_create_calendar_event_even_with_approval() -> None:
    decision = PolicyEngine().evaluate(
        PolicyEvaluationRequest(
            actor=ActorRole.DISCOVERY,
            capability=Capability.CALENDAR_EVENT_CREATE,
            approval_present=True,
        )
    )

    assert decision.allowed is False
    assert decision.rule_id == "role.default_deny"


def test_builder_is_blocked_before_implementation_state() -> None:
    decision = PolicyEngine().evaluate(
        PolicyEvaluationRequest(
            actor=ActorRole.BUILDER,
            capability=Capability.REPOSITORY_WRITE,
            workflow_state=WorkflowState.SPEC_REVIEW,
            resource="agentos/demo-workflow",
        )
    )

    assert decision.allowed is False
    assert decision.rule_id == "repository.workflow_state"


def test_builder_can_write_only_allowlisted_branch_during_implementation() -> None:
    engine = PolicyEngine()
    allowed = engine.evaluate(
        PolicyEvaluationRequest(
            actor=ActorRole.BUILDER,
            capability=Capability.REPOSITORY_WRITE,
            workflow_state=WorkflowState.IMPLEMENTING,
            resource="agentos/demo-workflow",
        )
    )
    denied = engine.evaluate(
        PolicyEvaluationRequest(
            actor=ActorRole.BUILDER,
            capability=Capability.REPOSITORY_WRITE,
            workflow_state=WorkflowState.IMPLEMENTING,
            resource="main",
        )
    )

    assert allowed.allowed is True
    assert denied.allowed is False
    assert denied.rule_id == "repository.branch_jail"


def test_production_deployment_is_globally_disabled() -> None:
    decision = PolicyEngine().evaluate(
        PolicyEvaluationRequest(
            actor=ActorRole.RELEASE_SERVICE,
            capability=Capability.DEPLOYMENT_PRODUCTION,
            workflow_state=WorkflowState.RELEASE_APPROVED,
            approval_present=True,
        )
    )

    assert decision.allowed is False
    assert decision.rule_id == "global.explicit_deny"

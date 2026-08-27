from app.contracts import (
    ActorRole,
    ArtifactCreateRequest,
    EngagementCreateRequest,
    MeetingMode,
    OrganizationCreateRequest,
    TransitionRequest,
    WorkforceActivationRequest,
)
from app.orchestration.context import ContextAssembler
from app.platform.artifacts import InMemoryArtifactStore
from app.platform.organizations import InMemoryOrganizationStore
from app.platform.workflow import InMemoryWorkflowEngine


def _platform() -> tuple[
    InMemoryWorkflowEngine,
    InMemoryArtifactStore,
    InMemoryOrganizationStore,
    ContextAssembler,
    str,
]:
    workflows = InMemoryWorkflowEngine()
    artifacts = InMemoryArtifactStore()
    organizations = InMemoryOrganizationStore()
    organization = organizations.create(
        OrganizationCreateRequest(
            display_name="Acme Software",
            owner_name="Asha Rao",
            owner_email="asha@example.com",
            company_size="11-50",
            idempotency_key="context-org-v1",
        )
    )
    workforce = organizations.activate(
        organization.organization_id,
        WorkforceActivationRequest(
            template_id="software_delivery_v1",
            display_name="Delivery Workforce",
            meeting_mode=MeetingMode.AGENT_OS_ROOM,
            repository_url="https://github.com/acme/product",
            base_branch="main",
            working_branch_prefix="agentos/",
            specification_approver_email="asha@example.com",
            release_approver_email="asha@example.com",
            idempotency_key="context-workforce-v1",
        ),
    )
    engagement = EngagementCreateRequest(
        workforce_id=workforce.workforce_id,
        client_name="Orbit Retail",
        project_name="Customer operations portal",
        client_contact_name="Ravi Shah",
        client_contact_email="ravi@orbit.example",
        client_request="Build a controlled customer operations request portal.",
        idempotency_key="context-engagement-v1",
    )
    from app.contracts import WorkflowCreateRequest

    workflow = workflows.create(
        WorkflowCreateRequest(
            name=engagement.project_name,
            client_request=engagement.client_request,
            tenant_id=organization.tenant_id,
            organization_id=organization.organization_id,
            workforce_id=workforce.workforce_id,
            client_name=engagement.client_name,
            client_contact_name=engagement.client_contact_name,
            client_contact_email=engagement.client_contact_email,
            idempotency_key=engagement.idempotency_key,
        )
    )
    contexts = ContextAssembler(
        workflows=workflows,
        artifacts=artifacts,
        organizations=organizations,
    )
    return workflows, artifacts, organizations, contexts, workflow.workflow_id


def test_discovery_context_is_scoped_and_has_no_repository_boundary() -> None:
    _, _, _, contexts, workflow_id = _platform()

    context = contexts.build(workflow_id, ActorRole.DISCOVERY, trace_id="trace-discovery")

    assert context.workflow_id == workflow_id
    assert context.client.client_name == "Orbit Retail"
    assert context.repository_boundary is None
    assert context.artifact_references == []
    assert context.trace_id == "trace-discovery"


def test_planner_receives_only_approved_specification_reference() -> None:
    workflows, artifacts, _, contexts, workflow_id = _platform()
    workflows.transition(
        workflow_id,
        TransitionRequest(
            action="start_discovery",
            actor=ActorRole.MANAGER,
            idempotency_key="context-start-discovery",
        ),
    )
    specification = artifacts.create(
        workflow_id,
        ArtifactCreateRequest(
            logical_name="SPECIFICATIONS",
            kind="text/markdown",
            content="# Approved specification",
            actor=ActorRole.DISCOVERY,
            idempotency_key="context-specification-v1",
        ),
    )
    artifacts.approve(
        workflow_id,
        specification.artifact_id,
        ActorRole.HUMAN,
        specification.sha256,
    )
    artifacts.create(
        workflow_id,
        ArtifactCreateRequest(
            logical_name="DISCOVERY_RECORD",
            kind="application/json",
            content='{"confirmed": true}',
            actor=ActorRole.DISCOVERY,
            idempotency_key="context-discovery-record-v1",
        ),
    )
    workflows.transition(
        workflow_id,
        TransitionRequest(
            action="submit_specification",
            actor=ActorRole.DISCOVERY,
            idempotency_key="context-submit-specification",
        ),
    )
    workflows.transition(
        workflow_id,
        TransitionRequest(
            action="approve_specification",
            actor=ActorRole.HUMAN,
            idempotency_key="context-approve-specification",
        ),
    )

    context = contexts.build(workflow_id, ActorRole.PLANNER)

    assert [item.logical_name for item in context.artifact_references] == ["SPECIFICATIONS"]
    assert context.artifact_references[0].approved is True
    assert context.artifact_references[0].immutable is True
    assert context.repository_boundary is not None
    assert context.repository_boundary.working_branch_prefix == "agentos/"

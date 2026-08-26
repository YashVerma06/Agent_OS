from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class ActorRole(StrEnum):
    MANAGER = "manager"
    DISCOVERY = "discovery"
    PLANNER = "planner"
    BUILDER = "builder"
    REVIEWER = "reviewer"
    RELEASE_SERVICE = "release_service"
    HUMAN = "human"


class WorkflowState(StrEnum):
    INTAKE = "INTAKE"
    DISCOVERY = "DISCOVERY"
    SPEC_REVIEW = "SPEC_REVIEW"
    PLANNING = "PLANNING"
    IMPLEMENTING = "IMPLEMENTING"
    REVIEWING = "REVIEWING"
    REVISION_REQUIRED = "REVISION_REQUIRED"
    RELEASE_REVIEW = "RELEASE_REVIEW"
    RELEASE_APPROVED = "RELEASE_APPROVED"
    STAGING_RELEASED = "STAGING_RELEASED"
    REJECTED = "REJECTED"


class Capability(StrEnum):
    WORKFLOW_INSPECT = "workflow.inspect"
    AGENT_DELEGATE = "agent.delegate"
    CALENDAR_EVENT_CREATE = "calendar.event.create"
    ARTIFACT_SPECIFICATION_WRITE = "artifact.specification.write"
    ARTIFACT_PLAN_WRITE = "artifact.plan.write"
    REPOSITORY_READ = "repository.read"
    REPOSITORY_WRITE = "repository.write"
    TEST_RUN = "test.run"
    SECURITY_SCAN = "security.scan"
    APPROVAL_DECIDE = "approval.decide"
    DEPLOYMENT_STAGING = "deployment.staging"
    DEPLOYMENT_PRODUCTION = "deployment.production"
    SECRET_READ = "secret.read"
    PROTECTED_BRANCH_WRITE = "protected_branch.write"


class MeetingMode(StrEnum):
    AGENT_OS_ROOM = "agent_os_room"
    TRANSCRIPT_UPLOAD = "transcript_upload"
    WRITTEN_BRIEF = "written_brief"


class AgentRunStatus(StrEnum):
    READY = "READY"
    COMPLETED = "COMPLETED"
    WAITING_FOR_HUMAN = "WAITING_FOR_HUMAN"
    DENIED = "DENIED"
    FAILED = "FAILED"


class HandoffGate(StrEnum):
    NONE = "NONE"
    SPECIFICATION_APPROVAL = "SPECIFICATION_APPROVAL"
    RELEASE_APPROVAL = "RELEASE_APPROVAL"


class OrganizationCreateRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=120)
    legal_name: str | None = Field(default=None, max_length=180)
    owner_name: str = Field(min_length=2, max_length=120)
    owner_email: str = Field(min_length=5, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    company_size: Literal["1-10", "11-50", "51-200", "201-1000", "1000+"]
    idempotency_key: str = Field(default_factory=lambda: str(uuid4()), min_length=8, max_length=160)


class OrganizationProfile(BaseModel):
    organization_id: str
    tenant_id: str
    display_name: str
    legal_name: str | None = None
    owner_name: str
    owner_email: str
    company_size: str
    identity_status: Literal["UNVERIFIED_FOUNDATION"] = "UNVERIFIED_FOUNDATION"
    created_at: datetime = Field(default_factory=utc_now)


class WorkforceTemplate(BaseModel):
    template_id: str
    display_name: str
    description: str
    agent_roles: list[ActorRole]
    human_gates: list[str]
    version: int = 1


class WorkforceActivationRequest(BaseModel):
    template_id: str = Field(min_length=3, max_length=100)
    display_name: str = Field(min_length=3, max_length=120)
    meeting_mode: MeetingMode
    repository_url: str = Field(
        min_length=19,
        max_length=300,
        pattern=r"^https://github\.com/[^/\s]+/[^/\s]+/?$",
    )
    base_branch: str = Field(default="main", min_length=1, max_length=120)
    working_branch_prefix: str = Field(default="agentos/", min_length=2, max_length=80)
    specification_approver_email: str = Field(
        min_length=5,
        max_length=254,
        pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$",
    )
    release_approver_email: str = Field(
        min_length=5,
        max_length=254,
        pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$",
    )
    idempotency_key: str = Field(default_factory=lambda: str(uuid4()), min_length=8, max_length=160)


class ActivatedWorkforce(BaseModel):
    workforce_id: str
    organization_id: str
    template_id: str
    display_name: str
    meeting_mode: MeetingMode
    repository_url: str
    base_branch: str
    working_branch_prefix: str
    specification_approver_email: str
    release_approver_email: str
    status: Literal["CONFIGURED"] = "CONFIGURED"
    integration_status: dict[str, str] = Field(
        default_factory=lambda: {
            "meeting": "configuration_saved",
            "github": "boundary_saved_not_connected",
            "calendar": "not_connected",
        }
    )
    created_at: datetime = Field(default_factory=utc_now)


class EngagementCreateRequest(BaseModel):
    workforce_id: str = Field(min_length=8, max_length=160)
    client_name: str = Field(min_length=2, max_length=160)
    project_name: str = Field(min_length=3, max_length=160)
    client_contact_name: str | None = Field(default=None, max_length=120)
    client_contact_email: str | None = Field(
        default=None,
        max_length=254,
        pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$",
    )
    client_request: str = Field(min_length=20, max_length=10_000)
    idempotency_key: str = Field(default_factory=lambda: str(uuid4()), min_length=8, max_length=160)


class WorkflowCreateRequest(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    client_request: str = Field(min_length=10, max_length=10_000)
    tenant_id: str = Field(default="agent-os-labs", min_length=3, max_length=120)
    organization_id: str | None = None
    workforce_id: str | None = None
    client_name: str | None = Field(default=None, max_length=160)
    client_contact_name: str | None = Field(default=None, max_length=120)
    client_contact_email: str | None = Field(default=None, max_length=254)
    idempotency_key: str = Field(default_factory=lambda: str(uuid4()), min_length=8, max_length=160)


class WorkflowSnapshot(BaseModel):
    workflow_id: str
    tenant_id: str
    name: str
    client_request: str
    organization_id: str | None = None
    workforce_id: str | None = None
    client_name: str | None = None
    client_contact_name: str | None = None
    client_contact_email: str | None = None
    state: WorkflowState = WorkflowState.INTAKE
    version: int = 1
    reviewer_passed: bool = False
    release_approved: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class TransitionRequest(BaseModel):
    action: str = Field(min_length=3, max_length=80)
    actor: ActorRole
    idempotency_key: str = Field(min_length=8, max_length=160)
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    workflow_id: str
    actor: ActorRole
    action: str
    state_before: WorkflowState
    state_after: WorkflowState
    allowed: bool
    reason: str
    rule_id: str
    idempotency_key: str
    trace_id: str
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TransitionResult(BaseModel):
    workflow: WorkflowSnapshot
    audit_event: AuditEvent
    replayed: bool = False


class PolicyEvaluationRequest(BaseModel):
    actor: ActorRole
    capability: Capability
    workflow_state: WorkflowState | None = None
    resource: str | None = None
    approval_present: bool = False
    trace_id: str = Field(default_factory=lambda: str(uuid4()))


class PolicyDecision(BaseModel):
    allowed: bool
    actor: ActorRole
    capability: Capability
    reason: str
    rule_id: str
    workflow_state: WorkflowState | None = None
    resource: str | None = None
    trace_id: str


class ArtifactCreateRequest(BaseModel):
    logical_name: str = Field(min_length=3, max_length=160)
    kind: str = Field(min_length=3, max_length=80)
    content: str = Field(min_length=1, max_length=1_000_000)
    actor: ActorRole
    source_artifact_ids: list[str] = Field(default_factory=list)
    idempotency_key: str = Field(default_factory=lambda: str(uuid4()), min_length=8, max_length=160)


class ArtifactVersion(BaseModel):
    artifact_id: str = Field(default_factory=lambda: str(uuid4()))
    workflow_id: str
    logical_name: str
    kind: str
    version: int
    content: str
    sha256: str
    source_artifact_ids: list[str] = Field(default_factory=list)
    generated_by: ActorRole
    approved: bool = False
    approved_by: ActorRole | None = None
    immutable: bool = False
    created_at: datetime = Field(default_factory=utc_now)


class ArtifactApprovalRequest(BaseModel):
    actor: ActorRole
    expected_sha256: str = Field(min_length=64, max_length=64)


class ArtifactReference(BaseModel):
    """Content-free artifact pointer safe to pass between specialist agents."""

    artifact_id: str
    logical_name: str
    kind: str
    version: int = Field(ge=1)
    sha256: str = Field(min_length=64, max_length=64)
    generated_by: ActorRole
    approved: bool
    immutable: bool
    source_artifact_ids: list[str] = Field(default_factory=list)


class RepositoryBoundary(BaseModel):
    repository_url: str = Field(
        min_length=19,
        max_length=300,
        pattern=r"^https://github\.com/[^/\s]+/[^/\s]+/?$",
    )
    base_branch: str = Field(min_length=1, max_length=120)
    working_branch_prefix: str = Field(min_length=2, max_length=80)


class ClientContext(BaseModel):
    client_name: str | None = Field(default=None, max_length=160)
    contact_name: str | None = Field(default=None, max_length=120)
    contact_email: str | None = Field(default=None, max_length=254)
    project_name: str = Field(min_length=3, max_length=120)
    initial_request: str = Field(min_length=10, max_length=10_000)


class ContextManifest(BaseModel):
    """Minimum-authority, tenant-scoped input assembled for one agent run."""

    workflow_id: str
    tenant_id: str
    organization_id: str | None = None
    workforce_id: str | None = None
    workflow_state: WorkflowState
    workflow_version: int = Field(ge=1)
    target_agent: ActorRole
    client: ClientContext
    artifact_references: list[ArtifactReference] = Field(default_factory=list)
    repository_boundary: RepositoryBoundary | None = None
    candidate_capabilities: list[Capability] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=utc_now)


class HandoffEnvelope(BaseModel):
    """An agent proposal that still requires deterministic workflow validation."""

    workflow_id: str
    from_agent: ActorRole
    requested_next_agent: ActorRole | None = None
    output_artifact_ids: list[str] = Field(default_factory=list)
    required_gate: HandoffGate = HandoffGate.NONE
    status: AgentRunStatus
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    idempotency_key: str = Field(min_length=8, max_length=160)


class AgentRunRequest(BaseModel):
    workflow_id: str
    target_agent: ActorRole
    context: ContextManifest
    input_artifact_ids: list[str] = Field(default_factory=list)
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    idempotency_key: str = Field(min_length=8, max_length=160)


class AgentRunResult(BaseModel):
    workflow_id: str
    agent: ActorRole
    status: AgentRunStatus
    output_artifact_ids: list[str] = Field(default_factory=list)
    summary: str = Field(default="", max_length=4_000)
    handoff: HandoffEnvelope | None = None
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    replayed: bool = False


class NextActionRequest(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=160)
    trace_id: str = Field(default_factory=lambda: str(uuid4()))


class OrchestrationDecision(BaseModel):
    workflow_id: str
    workflow_state: WorkflowState
    status: AgentRunStatus
    target_agent: ActorRole | None = None
    required_gate: HandoffGate = HandoffGate.NONE
    reason: str
    run_request: AgentRunRequest | None = None
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    replayed: bool = False


class ApprovalRecord(BaseModel):
    approval_id: str = Field(default_factory=lambda: str(uuid4()))
    workflow_id: str
    artifact_id: str
    artifact_sha256: str = Field(min_length=64, max_length=64)
    gate: HandoffGate
    actor: Literal[ActorRole.HUMAN] = ActorRole.HUMAN
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=utc_now)


class MeetingSessionSummary(BaseModel):
    meeting_id: str
    workflow_id: str
    mode: MeetingMode
    status: Literal["CREATED", "LIVE", "FINALIZING", "COMPLETED", "FAILED"]
    transcript_artifact_id: str | None = None
    discovery_artifact_id: str | None = None
    specification_artifact_id: str | None = None
    trace_id: str = Field(default_factory=lambda: str(uuid4()))

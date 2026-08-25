from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
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


class WorkflowCreateRequest(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    client_request: str = Field(min_length=10, max_length=10_000)
    tenant_id: str = Field(default="agent-os-labs", min_length=3, max_length=120)


class WorkflowSnapshot(BaseModel):
    workflow_id: str
    tenant_id: str
    name: str
    client_request: str
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

from __future__ import annotations

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.api.meeting_routes import router as meeting_router
from app.api.workflow_routes import create_orchestration_router
from app.contracts import (
    ActivatedWorkforce,
    ArtifactApprovalRequest,
    ArtifactCreateRequest,
    ArtifactVersion,
    AuditEvent,
    EngagementCreateRequest,
    OrganizationCreateRequest,
    OrganizationProfile,
    PolicyDecision,
    PolicyEvaluationRequest,
    TransitionRequest,
    TransitionResult,
    WorkflowCreateRequest,
    WorkflowSnapshot,
    WorkforceActivationRequest,
    WorkforceTemplate,
)
from app.orchestration.context import ContextAssembler
from app.orchestration.runner import OrchestrationCoordinator
from app.platform.artifacts import ArtifactError, InMemoryArtifactStore
from app.platform.organizations import (
    InMemoryOrganizationStore,
    OnboardingError,
    OnboardingIdempotencyConflict,
    OrganizationNotFound,
    WorkforceNotFound,
)
from app.platform.policy import PolicyEngine
from app.platform.workflow import (
    IdempotencyConflict,
    InMemoryWorkflowEngine,
    TransitionDenied,
    WorkflowNotFound,
)
from app.settings import get_settings
from app.workforce import workforce_contract

api = FastAPI(
    title="Agent OS Control Plane",
    version="0.1.0",
    description="Deterministic workflow, policy, artifact, and audit foundation.",
)
settings = get_settings()
api.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Trace-Id"],
)
workflows = InMemoryWorkflowEngine()
artifacts = InMemoryArtifactStore()
policy = PolicyEngine()
organizations = InMemoryOrganizationStore()
contexts = ContextAssembler(
    workflows=workflows,
    artifacts=artifacts,
    organizations=organizations,
)
orchestration = OrchestrationCoordinator(
    workflows=workflows,
    artifacts=artifacts,
    contexts=contexts,
)
api.include_router(create_orchestration_router(orchestration))
api.include_router(meeting_router)


@api.get("/health")
def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "service": "agent-os-control-plane",
        "google_cloud_project": settings.google_cloud_project,
        "google_cloud_location": settings.google_cloud_location,
        "model": settings.gemini_core_model,
        "vertex_ai": settings.google_genai_use_vertexai,
        "persistence": "in_memory_foundation",
    }


@api.get("/v1/workforce")
def get_workforce() -> list[dict[str, object]]:
    return workforce_contract()


@api.get("/v1/workforce-templates", response_model=list[WorkforceTemplate])
def get_workforce_templates() -> list[WorkforceTemplate]:
    return organizations.templates()


@api.post(
    "/v1/organizations",
    response_model=OrganizationProfile,
    status_code=status.HTTP_201_CREATED,
)
def create_organization(request: OrganizationCreateRequest) -> OrganizationProfile:
    try:
        return organizations.create(request)
    except OnboardingIdempotencyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@api.get("/v1/organizations/{organization_id}", response_model=OrganizationProfile)
def get_organization(organization_id: str) -> OrganizationProfile:
    try:
        return organizations.get(organization_id)
    except OrganizationNotFound as exc:
        raise HTTPException(status_code=404, detail="Organization not found.") from exc


@api.post(
    "/v1/organizations/{organization_id}/workforces",
    response_model=ActivatedWorkforce,
    status_code=status.HTTP_201_CREATED,
)
def activate_workforce(
    organization_id: str, request: WorkforceActivationRequest
) -> ActivatedWorkforce:
    try:
        return organizations.activate(organization_id, request)
    except OrganizationNotFound as exc:
        raise HTTPException(status_code=404, detail="Organization not found.") from exc
    except OnboardingIdempotencyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except OnboardingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@api.get(
    "/v1/organizations/{organization_id}/workforces/{workforce_id}",
    response_model=ActivatedWorkforce,
)
def get_activated_workforce(
    organization_id: str, workforce_id: str
) -> ActivatedWorkforce:
    try:
        return organizations.get_workforce(organization_id, workforce_id)
    except (OrganizationNotFound, WorkforceNotFound) as exc:
        raise HTTPException(status_code=404, detail="Activated workforce not found.") from exc


@api.post(
    "/v1/organizations/{organization_id}/engagements",
    response_model=WorkflowSnapshot,
    status_code=status.HTTP_201_CREATED,
)
def create_engagement(
    organization_id: str, request: EngagementCreateRequest
) -> WorkflowSnapshot:
    try:
        organization = organizations.get(organization_id)
        organizations.get_workforce(organization_id, request.workforce_id)
    except (OrganizationNotFound, WorkforceNotFound) as exc:
        raise HTTPException(status_code=404, detail="Organization or workforce not found.") from exc

    return workflows.create(
        WorkflowCreateRequest(
            name=request.project_name,
            client_request=request.client_request,
            tenant_id=organization.tenant_id,
            organization_id=organization.organization_id,
            workforce_id=request.workforce_id,
            client_name=request.client_name,
            client_contact_name=request.client_contact_name,
            client_contact_email=request.client_contact_email,
            idempotency_key=request.idempotency_key,
        )
    )


@api.post("/v1/workflows", response_model=WorkflowSnapshot, status_code=status.HTTP_201_CREATED)
def create_workflow(request: WorkflowCreateRequest) -> WorkflowSnapshot:
    try:
        return workflows.create(request)
    except IdempotencyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@api.get("/v1/workflows/{workflow_id}", response_model=WorkflowSnapshot)
def get_workflow(workflow_id: str) -> WorkflowSnapshot:
    try:
        return workflows.get(workflow_id)
    except WorkflowNotFound as exc:
        raise HTTPException(status_code=404, detail="Workflow not found.") from exc


@api.post("/v1/workflows/{workflow_id}/transitions", response_model=TransitionResult)
def transition_workflow(workflow_id: str, request: TransitionRequest) -> TransitionResult:
    try:
        if request.action == "approve_specification":
            approved_sha256 = request.metadata.get("approved_sha256")
            specifications = [
                artifact
                for artifact in artifacts.list(workflow_id)
                if artifact.logical_name == "SPECIFICATIONS"
            ]
            latest_specification = (
                max(specifications, key=lambda artifact: artifact.version)
                if specifications
                else None
            )
            matching_approval = (
                latest_specification
                if latest_specification is not None
                and latest_specification.sha256 == approved_sha256
                and latest_specification.approved
                and latest_specification.immutable
                else None
            )
            if matching_approval is None:
                audit = workflows.record_denial(
                    workflow_id,
                    request,
                    reason=(
                        "Specification transition requires an approved immutable artifact "
                        "matching metadata.approved_sha256 for the latest specification."
                    ),
                    rule_id="gate.specification_artifact_missing",
                )
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": audit.reason,
                        "audit_event": audit.model_dump(mode="json"),
                    },
                )
        return workflows.transition(workflow_id, request)
    except WorkflowNotFound as exc:
        raise HTTPException(status_code=404, detail="Workflow not found.") from exc
    except IdempotencyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TransitionDenied as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(exc),
                "audit_event": exc.audit_event.model_dump(mode="json"),
            },
        ) from exc


@api.get("/v1/workflows/{workflow_id}/audit", response_model=list[AuditEvent])
def get_audit(workflow_id: str) -> list[AuditEvent]:
    try:
        return workflows.audit(workflow_id)
    except WorkflowNotFound as exc:
        raise HTTPException(status_code=404, detail="Workflow not found.") from exc


@api.post(
    "/v1/workflows/{workflow_id}/artifacts",
    response_model=ArtifactVersion,
    status_code=status.HTTP_201_CREATED,
)
def create_artifact(workflow_id: str, request: ArtifactCreateRequest) -> ArtifactVersion:
    try:
        workflows.get(workflow_id)
    except WorkflowNotFound as exc:
        raise HTTPException(status_code=404, detail="Workflow not found.") from exc
    try:
        return artifacts.create(workflow_id, request)
    except ArtifactError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@api.get("/v1/workflows/{workflow_id}/artifacts", response_model=list[ArtifactVersion])
def list_artifacts(workflow_id: str) -> list[ArtifactVersion]:
    try:
        workflows.get(workflow_id)
    except WorkflowNotFound as exc:
        raise HTTPException(status_code=404, detail="Workflow not found.") from exc
    return artifacts.list(workflow_id)


@api.post(
    "/v1/workflows/{workflow_id}/artifacts/{artifact_id}/approve",
    response_model=ArtifactVersion,
)
def approve_artifact(
    workflow_id: str, artifact_id: str, request: ArtifactApprovalRequest
) -> ArtifactVersion:
    try:
        return artifacts.approve(
            workflow_id=workflow_id,
            artifact_id=artifact_id,
            actor=request.actor,
            expected_sha256=request.expected_sha256,
        )
    except ArtifactError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@api.post("/v1/policy/evaluate", response_model=PolicyDecision)
def evaluate_policy(request: PolicyEvaluationRequest) -> PolicyDecision:
    return policy.evaluate(request)

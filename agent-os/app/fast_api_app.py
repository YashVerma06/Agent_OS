from __future__ import annotations

from fastapi import FastAPI, HTTPException, status

from app.contracts import (
    ArtifactApprovalRequest,
    ArtifactCreateRequest,
    ArtifactVersion,
    AuditEvent,
    PolicyDecision,
    PolicyEvaluationRequest,
    TransitionRequest,
    TransitionResult,
    WorkflowCreateRequest,
    WorkflowSnapshot,
)
from app.platform.artifacts import ArtifactError, InMemoryArtifactStore
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
workflows = InMemoryWorkflowEngine()
artifacts = InMemoryArtifactStore()
policy = PolicyEngine()


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


@api.post("/v1/workflows", response_model=WorkflowSnapshot, status_code=status.HTTP_201_CREATED)
def create_workflow(request: WorkflowCreateRequest) -> WorkflowSnapshot:
    return workflows.create(request)


@api.get("/v1/workflows/{workflow_id}", response_model=WorkflowSnapshot)
def get_workflow(workflow_id: str) -> WorkflowSnapshot:
    try:
        return workflows.get(workflow_id)
    except WorkflowNotFound as exc:
        raise HTTPException(status_code=404, detail="Workflow not found.") from exc


@api.post("/v1/workflows/{workflow_id}/transitions", response_model=TransitionResult)
def transition_workflow(workflow_id: str, request: TransitionRequest) -> TransitionResult:
    try:
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

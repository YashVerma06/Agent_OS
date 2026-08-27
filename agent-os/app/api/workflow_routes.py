from fastapi import APIRouter, HTTPException

from app.contracts import (
    AgentRunResult,
    NextActionRequest,
    OrchestrationDecision,
)
from app.orchestration.context import ContextBuildError
from app.orchestration.handoff import HandoffDenied
from app.orchestration.runner import (
    OrchestrationCoordinator,
    OrchestrationError,
    OrchestrationIdempotencyConflict,
)
from app.platform.workflow import WorkflowNotFound


def create_orchestration_router(coordinator: OrchestrationCoordinator) -> APIRouter:
    router = APIRouter(prefix="/v1/workflows", tags=["orchestration"])

    @router.post(
        "/{workflow_id}/orchestration/next",
        response_model=OrchestrationDecision,
    )
    def prepare_next(
        workflow_id: str, request: NextActionRequest
    ) -> OrchestrationDecision:
        try:
            return coordinator.prepare_next(workflow_id, request)
        except WorkflowNotFound as exc:
            raise HTTPException(status_code=404, detail="Workflow not found.") from exc
        except OrchestrationIdempotencyConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (ContextBuildError, HandoffDenied, OrchestrationError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post(
        "/{workflow_id}/agent-runs/validate",
        response_model=AgentRunResult,
    )
    def validate_agent_result(
        workflow_id: str, result: AgentRunResult
    ) -> AgentRunResult:
        if result.workflow_id != workflow_id:
            raise HTTPException(
                status_code=409,
                detail="Agent result belongs to a different workflow.",
            )
        try:
            return coordinator.validate_result(result)
        except WorkflowNotFound as exc:
            raise HTTPException(status_code=404, detail="Workflow not found.") from exc
        except (HandoffDenied, OrchestrationError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return router

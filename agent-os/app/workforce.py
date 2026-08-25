from __future__ import annotations

from pydantic import BaseModel

from app.contracts import ActorRole


class AgentDefinition(BaseModel):
    role: ActorRole
    display_name: str
    purpose: str
    outputs: tuple[str, ...]
    forbidden: tuple[str, ...]


WORKFORCE: tuple[AgentDefinition, ...] = (
    AgentDefinition(
        role=ActorRole.MANAGER,
        display_name="Workforce Manager",
        purpose="Inspect workflow status, delegate to the correct specialist, and request gates.",
        outputs=("WORKFORCE_ASSIGNMENT", "APPROVAL_REQUEST"),
        forbidden=("approval.decide", "repository.write", "deployment.*", "iam.grant"),
    ),
    AgentDefinition(
        role=ActorRole.DISCOVERY,
        display_name="Discovery & Specification Agent",
        purpose="Clarify the client request and produce an evidence-backed specification.",
        outputs=("MEETING_TRANSCRIPT", "DISCOVERY_RECORD", "SPECIFICATIONS"),
        forbidden=("calendar.event.create", "repository.*", "approval.decide"),
    ),
    AgentDefinition(
        role=ActorRole.PLANNER,
        display_name="Planner & Architect Agent",
        purpose="Turn the approved specification into traceable tasks and architecture notes.",
        outputs=("BUILD_PLAN", "ARCHITECTURE_NOTES"),
        forbidden=("requirements.change", "repository.write", "approval.decide"),
    ),
    AgentDefinition(
        role=ActorRole.BUILDER,
        display_name="Builder Agent",
        purpose="Create a bounded code change and run the allowlisted build profile.",
        outputs=("PATCH", "BUILD_EVIDENCE"),
        forbidden=("protected_branch.write", "secret.read", "specification.write", "deployment.*"),
    ),
    AgentDefinition(
        role=ActorRole.REVIEWER,
        display_name="Reviewer Agent",
        purpose="Perform requirement-linked QA and security review independently of the Builder.",
        outputs=("REVIEW_REPORT", "REVISION_REQUEST"),
        forbidden=("repository.write", "finding.waive", "approval.decide", "deployment.*"),
    ),
)


def workforce_contract() -> list[dict[str, object]]:
    return [agent.model_dump(mode="json") for agent in WORKFORCE]

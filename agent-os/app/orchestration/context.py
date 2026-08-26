from __future__ import annotations

from uuid import uuid4

from app.contracts import (
    ActorRole,
    ArtifactReference,
    ArtifactVersion,
    ClientContext,
    ContextManifest,
    RepositoryBoundary,
    WorkflowSnapshot,
)
from app.orchestration.handoff import validate_delegation
from app.platform.artifacts import InMemoryArtifactStore
from app.platform.organizations import (
    InMemoryOrganizationStore,
    OrganizationNotFound,
    WorkforceNotFound,
)
from app.platform.policy import candidate_capabilities_for
from app.platform.workflow import InMemoryWorkflowEngine


class ContextBuildError(ValueError):
    pass


VISIBLE_ARTIFACTS: dict[ActorRole, frozenset[str] | None] = {
    ActorRole.MANAGER: None,
    ActorRole.DISCOVERY: frozenset(
        {"MEETING_TRANSCRIPT", "DISCOVERY_RECORD", "SPECIFICATIONS"}
    ),
    ActorRole.PLANNER: frozenset({"SPECIFICATIONS"}),
    ActorRole.BUILDER: frozenset(
        {"SPECIFICATIONS", "BUILD_PLAN", "ARCHITECTURE_NOTES"}
    ),
    ActorRole.REVIEWER: frozenset(
        {
            "SPECIFICATIONS",
            "BUILD_PLAN",
            "ARCHITECTURE_NOTES",
            "PATCH",
            "BUILD_EVIDENCE",
        }
    ),
    ActorRole.RELEASE_SERVICE: frozenset({"REVIEW_REPORT"}),
}


def _reference(artifact: ArtifactVersion) -> ArtifactReference:
    return ArtifactReference(
        artifact_id=artifact.artifact_id,
        logical_name=artifact.logical_name,
        kind=artifact.kind,
        version=artifact.version,
        sha256=artifact.sha256,
        generated_by=artifact.generated_by,
        approved=artifact.approved,
        immutable=artifact.immutable,
        source_artifact_ids=artifact.source_artifact_ids,
    )


def _latest_by_logical_name(artifacts: list[ArtifactVersion]) -> list[ArtifactVersion]:
    latest: dict[str, ArtifactVersion] = {}
    for artifact in artifacts:
        existing = latest.get(artifact.logical_name)
        if existing is None or artifact.version > existing.version:
            latest[artifact.logical_name] = artifact
    return sorted(latest.values(), key=lambda artifact: artifact.logical_name)


class ContextAssembler:
    """Build minimum-authority context manifests from deterministic platform state."""

    def __init__(
        self,
        *,
        workflows: InMemoryWorkflowEngine,
        artifacts: InMemoryArtifactStore,
        organizations: InMemoryOrganizationStore,
    ) -> None:
        self._workflows = workflows
        self._artifacts = artifacts
        self._organizations = organizations

    def build(
        self,
        workflow_id: str,
        target_agent: ActorRole,
        *,
        trace_id: str | None = None,
    ) -> ContextManifest:
        snapshot = self._workflows.get(workflow_id)
        validate_delegation(snapshot, target_agent)

        artifacts = _latest_by_logical_name(self._artifacts.list(workflow_id))
        visible_names = VISIBLE_ARTIFACTS.get(target_agent, frozenset())
        visible = artifacts if visible_names is None else [
            artifact for artifact in artifacts if artifact.logical_name in visible_names
        ]
        self._validate_required_sources(target_agent, visible)

        repository_boundary = self._repository_boundary(snapshot)
        if target_agent in {ActorRole.BUILDER, ActorRole.REVIEWER} and repository_boundary is None:
            raise ContextBuildError(
                f"{target_agent.value} requires an activated workforce repository boundary."
            )

        return ContextManifest(
            workflow_id=snapshot.workflow_id,
            tenant_id=snapshot.tenant_id,
            organization_id=snapshot.organization_id,
            workforce_id=snapshot.workforce_id,
            workflow_state=snapshot.state,
            workflow_version=snapshot.version,
            target_agent=target_agent,
            client=ClientContext(
                client_name=snapshot.client_name,
                contact_name=snapshot.client_contact_name,
                contact_email=snapshot.client_contact_email,
                project_name=snapshot.name,
                initial_request=snapshot.client_request,
            ),
            artifact_references=[_reference(artifact) for artifact in visible],
            repository_boundary=(
                repository_boundary
                if target_agent in {ActorRole.PLANNER, ActorRole.BUILDER, ActorRole.REVIEWER}
                else None
            ),
            candidate_capabilities=candidate_capabilities_for(target_agent),
            trace_id=trace_id or str(uuid4()),
        )

    def _repository_boundary(
        self, snapshot: WorkflowSnapshot
    ) -> RepositoryBoundary | None:
        organization_id = snapshot.organization_id
        workforce_id = snapshot.workforce_id
        if not organization_id or not workforce_id:
            return None
        try:
            workforce = self._organizations.get_workforce(organization_id, workforce_id)
        except (OrganizationNotFound, WorkforceNotFound) as exc:
            raise ContextBuildError("Activated workforce boundary could not be resolved.") from exc
        return RepositoryBoundary(
            repository_url=workforce.repository_url,
            base_branch=workforce.base_branch,
            working_branch_prefix=workforce.working_branch_prefix,
        )

    @staticmethod
    def _validate_required_sources(
        target_agent: ActorRole, artifacts: list[ArtifactVersion]
    ) -> None:
        by_name = {artifact.logical_name: artifact for artifact in artifacts}
        if target_agent in {ActorRole.PLANNER, ActorRole.BUILDER, ActorRole.REVIEWER}:
            specification = by_name.get("SPECIFICATIONS")
            if specification is None or not specification.approved or not specification.immutable:
                raise ContextBuildError(
                    f"{target_agent.value} requires an approved immutable specification."
                )
        if target_agent in {ActorRole.BUILDER, ActorRole.REVIEWER}:
            missing = {"BUILD_PLAN", "ARCHITECTURE_NOTES"} - by_name.keys()
            if missing:
                raise ContextBuildError(
                    f"{target_agent.value} context is missing: {', '.join(sorted(missing))}."
                )
        if target_agent == ActorRole.REVIEWER:
            missing = {"PATCH", "BUILD_EVIDENCE"} - by_name.keys()
            if missing:
                raise ContextBuildError(
                    f"Reviewer context is missing: {', '.join(sorted(missing))}."
                )

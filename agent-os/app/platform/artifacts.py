from __future__ import annotations

from collections import defaultdict
from hashlib import sha256

from app.contracts import ActorRole, ArtifactCreateRequest, ArtifactVersion


class ArtifactError(ValueError):
    pass


ALLOWED_ARTIFACTS: dict[ActorRole, frozenset[str]] = {
    ActorRole.MANAGER: frozenset({"WORKFORCE_ASSIGNMENT", "APPROVAL_REQUEST"}),
    ActorRole.DISCOVERY: frozenset({"MEETING_TRANSCRIPT", "DISCOVERY_RECORD", "SPECIFICATIONS"}),
    ActorRole.PLANNER: frozenset({"BUILD_PLAN", "ARCHITECTURE_NOTES"}),
    ActorRole.BUILDER: frozenset({"PATCH", "BUILD_EVIDENCE"}),
    ActorRole.REVIEWER: frozenset({"REVIEW_REPORT", "REVISION_REQUEST"}),
}


class InMemoryArtifactStore:
    """Reference implementation for immutable, hash-addressed artifact versions."""

    def __init__(self) -> None:
        self._artifacts: dict[str, ArtifactVersion] = {}
        self._versions: dict[tuple[str, str], list[str]] = defaultdict(list)
        self._idempotency: dict[
            tuple[str, str], tuple[tuple[object, ...], ArtifactVersion]
        ] = {}

    def create(self, workflow_id: str, request: ArtifactCreateRequest) -> ArtifactVersion:
        logical_name = request.logical_name.upper()
        if logical_name not in ALLOWED_ARTIFACTS.get(request.actor, frozenset()):
            raise ArtifactError(
                f"Actor {request.actor.value} cannot create artifact {logical_name}."
            )
        digest = sha256(request.content.encode("utf-8")).hexdigest()
        signature = (
            logical_name,
            request.kind,
            digest,
            request.actor,
            tuple(request.source_artifact_ids),
        )
        idempotency_slot = (workflow_id, request.idempotency_key)
        existing = self._idempotency.get(idempotency_slot)
        if existing is not None:
            existing_signature, existing_artifact = existing
            if existing_signature != signature:
                raise ArtifactError(
                    "The idempotency key was already used for different artifact content."
                )
            return existing_artifact.model_copy(deep=True)

        key = (workflow_id, logical_name)
        version = len(self._versions[key]) + 1
        artifact = ArtifactVersion(
            workflow_id=workflow_id,
            logical_name=logical_name,
            kind=request.kind,
            version=version,
            content=request.content,
            sha256=digest,
            source_artifact_ids=request.source_artifact_ids,
            generated_by=request.actor,
        )
        self._artifacts[artifact.artifact_id] = artifact
        self._versions[key].append(artifact.artifact_id)
        self._idempotency[idempotency_slot] = (signature, artifact)
        return artifact.model_copy(deep=True)

    def get(self, workflow_id: str, artifact_id: str) -> ArtifactVersion:
        artifact = self._artifacts.get(artifact_id)
        if artifact is None or artifact.workflow_id != workflow_id:
            raise ArtifactError("Artifact does not exist in this workflow.")
        return artifact.model_copy(deep=True)

    def list(self, workflow_id: str) -> list[ArtifactVersion]:
        return [
            artifact.model_copy(deep=True)
            for artifact in self._artifacts.values()
            if artifact.workflow_id == workflow_id
        ]

    def approve(
        self,
        workflow_id: str,
        artifact_id: str,
        actor: ActorRole,
        expected_sha256: str,
    ) -> ArtifactVersion:
        if actor != ActorRole.HUMAN:
            raise ArtifactError("Only an authenticated human may approve an artifact.")
        artifact = self._artifacts.get(artifact_id)
        if artifact is None or artifact.workflow_id != workflow_id:
            raise ArtifactError("Artifact does not exist in this workflow.")
        if artifact.sha256 != expected_sha256:
            raise ArtifactError("Artifact hash changed or does not match the approval request.")
        if artifact.approved:
            return artifact.model_copy(deep=True)
        approved = artifact.model_copy(
            update={"approved": True, "approved_by": actor, "immutable": True}, deep=True
        )
        self._artifacts[artifact_id] = approved
        return approved.model_copy(deep=True)

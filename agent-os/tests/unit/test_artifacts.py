import pytest

from app.contracts import ActorRole, ArtifactCreateRequest
from app.platform.artifacts import ArtifactError, InMemoryArtifactStore


def test_approved_artifact_is_hash_verified_and_immutable() -> None:
    store = InMemoryArtifactStore()
    artifact = store.create(
        "workflow-1",
        ArtifactCreateRequest(
            logical_name="SPECIFICATIONS",
            kind="markdown",
            content="# Approved specification",
            actor=ActorRole.DISCOVERY,
        ),
    )

    approved = store.approve(
        workflow_id="workflow-1",
        artifact_id=artifact.artifact_id,
        actor=ActorRole.HUMAN,
        expected_sha256=artifact.sha256,
    )

    assert approved.approved is True
    assert approved.immutable is True
    assert approved.sha256 == artifact.sha256


def test_artifact_approval_rejects_non_human_and_hash_mismatch() -> None:
    store = InMemoryArtifactStore()
    artifact = store.create(
        "workflow-1",
        ArtifactCreateRequest(
            logical_name="SPECIFICATIONS",
            kind="markdown",
            content="# Draft",
            actor=ActorRole.DISCOVERY,
        ),
    )

    with pytest.raises(ArtifactError):
        store.approve("workflow-1", artifact.artifact_id, ActorRole.MANAGER, artifact.sha256)
    with pytest.raises(ArtifactError):
        store.approve("workflow-1", artifact.artifact_id, ActorRole.HUMAN, "0" * 64)


def test_changes_create_a_new_artifact_version() -> None:
    store = InMemoryArtifactStore()
    first = store.create(
        "workflow-1",
        ArtifactCreateRequest(
            logical_name="SPECIFICATIONS",
            kind="markdown",
            content="# Version 1",
            actor=ActorRole.DISCOVERY,
        ),
    )
    second = store.create(
        "workflow-1",
        ArtifactCreateRequest(
            logical_name="SPECIFICATIONS",
            kind="markdown",
            content="# Version 2",
            actor=ActorRole.DISCOVERY,
            source_artifact_ids=[first.artifact_id],
        ),
    )

    assert first.version == 1
    assert second.version == 2
    assert first.sha256 != second.sha256


def test_artifact_role_boundary_is_enforced_outside_prompts() -> None:
    store = InMemoryArtifactStore()

    with pytest.raises(ArtifactError):
        store.create(
            "workflow-1",
            ArtifactCreateRequest(
                logical_name="PATCH",
                kind="diff",
                content="diff --git a/file b/file",
                actor=ActorRole.DISCOVERY,
            ),
        )


def test_artifact_creation_is_idempotent() -> None:
    store = InMemoryArtifactStore()
    request = ArtifactCreateRequest(
        logical_name="SPECIFICATIONS",
        kind="text/markdown",
        content="# Stable specification",
        actor=ActorRole.DISCOVERY,
        idempotency_key="specifications-v1",
    )

    first = store.create("workflow-1", request)
    replay = store.create("workflow-1", request)

    assert replay.artifact_id == first.artifact_id
    assert replay.version == 1
    assert len(store.list("workflow-1")) == 1

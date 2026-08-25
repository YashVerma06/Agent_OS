from fastapi.testclient import TestClient

from app.fast_api_app import api

client = TestClient(api)


def test_health_exposes_non_secret_platform_configuration() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["google_cloud_project"] == "agent-os-506220"
    assert payload["model"] == "gemini-3.6-flash"
    assert "secret" not in payload


def test_create_and_inspect_workflow() -> None:
    created = client.post(
        "/v1/workflows",
        json={
            "name": "Maintenance portal",
            "client_request": "Build a tenant maintenance request and manager workflow.",
        },
    )

    assert created.status_code == 201
    workflow = created.json()
    inspected = client.get(f"/v1/workflows/{workflow['workflow_id']}")
    assert inspected.status_code == 200
    assert inspected.json()["state"] == "INTAKE"


def test_local_control_room_origin_is_allowed() -> None:
    response = client.options(
        "/health",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"


def test_control_room_specification_approval_slice() -> None:
    created = client.post(
        "/v1/workflows",
        json={
            "name": "Northstar maintenance portal",
            "client_request": (
                "Build a tenant maintenance request form and a manager triage queue."
            ),
        },
    ).json()
    workflow_id = created["workflow_id"]

    discovery = client.post(
        f"/v1/workflows/{workflow_id}/transitions",
        json={
            "action": "start_discovery",
            "actor": "manager",
            "idempotency_key": f"{workflow_id}-start-discovery",
        },
    )
    assert discovery.status_code == 200
    assert discovery.json()["workflow"]["state"] == "DISCOVERY"

    specification = client.post(
        f"/v1/workflows/{workflow_id}/artifacts",
        json={
            "logical_name": "SPECIFICATIONS",
            "kind": "text/markdown",
            "content": "# Approved scope\n\nBuild the controlled maintenance portal.",
            "actor": "discovery",
            "idempotency_key": f"{workflow_id}-specifications-v1",
        },
    )
    assert specification.status_code == 201

    review = client.post(
        f"/v1/workflows/{workflow_id}/transitions",
        json={
            "action": "submit_specification",
            "actor": "discovery",
            "idempotency_key": f"{workflow_id}-submit-specification",
        },
    )
    assert review.json()["workflow"]["state"] == "SPEC_REVIEW"

    artifact = specification.json()
    approval = client.post(
        f"/v1/workflows/{workflow_id}/artifacts/{artifact['artifact_id']}/approve",
        json={"actor": "human", "expected_sha256": artifact["sha256"]},
    )
    assert approval.status_code == 200
    assert approval.json()["immutable"] is True

    planning = client.post(
        f"/v1/workflows/{workflow_id}/transitions",
        json={
            "action": "approve_specification",
            "actor": "human",
            "idempotency_key": f"{workflow_id}-approve-specification",
            "metadata": {"approved_sha256": artifact["sha256"]},
        },
    )
    assert planning.status_code == 200
    assert planning.json()["workflow"]["state"] == "PLANNING"

    policy_denial = client.post(
        "/v1/policy/evaluate",
        json={
            "actor": "builder",
            "capability": "deployment.production",
            "workflow_state": "PLANNING",
            "resource": "production",
        },
    )
    assert policy_denial.status_code == 200
    assert policy_denial.json()["allowed"] is False

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


def test_enterprise_can_register_activate_workforce_and_create_engagement() -> None:
    organization_response = client.post(
        "/v1/organizations",
        json={
            "display_name": "Acme Software",
            "owner_name": "Asha Rao",
            "owner_email": "asha@example.com",
            "company_size": "11-50",
            "idempotency_key": "api-acme-registration-v1",
        },
    )
    assert organization_response.status_code == 201
    organization = organization_response.json()

    workforce_response = client.post(
        f"/v1/organizations/{organization['organization_id']}/workforces",
        json={
            "template_id": "software_delivery_v1",
            "display_name": "Product Delivery Workforce",
            "meeting_mode": "agent_os_room",
            "repository_url": "https://github.com/acme/product",
            "base_branch": "main",
            "working_branch_prefix": "agentos/",
            "specification_approver_email": "asha@example.com",
            "release_approver_email": "asha@example.com",
            "idempotency_key": "api-acme-workforce-v1",
        },
    )
    assert workforce_response.status_code == 201
    workforce = workforce_response.json()

    engagement_response = client.post(
        f"/v1/organizations/{organization['organization_id']}/engagements",
        json={
            "workforce_id": workforce["workforce_id"],
            "client_name": "Orbit Retail",
            "project_name": "Customer operations portal",
            "client_contact_name": "Ravi Shah",
            "client_contact_email": "ravi@orbit.example",
            "client_request": (
                "Build a portal that lets the support team triage and resolve requests."
            ),
            "idempotency_key": "api-acme-engagement-v1",
        },
    )
    assert engagement_response.status_code == 201
    engagement = engagement_response.json()
    assert engagement["tenant_id"] == organization["tenant_id"]
    assert engagement["organization_id"] == organization["organization_id"]
    assert engagement["workforce_id"] == workforce["workforce_id"]
    assert engagement["client_name"] == "Orbit Retail"
    assert engagement["state"] == "INTAKE"

    replay = client.post(
        f"/v1/organizations/{organization['organization_id']}/engagements",
        json={
            "workforce_id": workforce["workforce_id"],
            "client_name": "Orbit Retail",
            "project_name": "Customer operations portal",
            "client_contact_name": "Ravi Shah",
            "client_contact_email": "ravi@orbit.example",
            "client_request": (
                "Build a portal that lets the support team triage and resolve requests."
            ),
            "idempotency_key": "api-acme-engagement-v1",
        },
    )
    assert replay.status_code == 201
    assert replay.json()["workflow_id"] == engagement["workflow_id"]


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

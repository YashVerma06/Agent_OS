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

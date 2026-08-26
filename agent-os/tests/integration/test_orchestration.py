from fastapi.testclient import TestClient

from app.fast_api_app import api

client = TestClient(api)


def test_orchestration_prepares_scoped_discovery_request_and_replays() -> None:
    workflow = client.post(
        "/v1/workflows",
        json={
            "name": "Orchestration slice",
            "client_request": "Build a controlled orchestration demonstration application.",
        },
    ).json()
    client.post(
        f"/v1/workflows/{workflow['workflow_id']}/transitions",
        json={
            "action": "start_discovery",
            "actor": "manager",
            "idempotency_key": f"{workflow['workflow_id']}-start-discovery",
        },
    )
    payload = {
        "idempotency_key": f"{workflow['workflow_id']}-prepare-discovery",
        "trace_id": "trace-orchestration-discovery",
    }

    prepared = client.post(
        f"/v1/workflows/{workflow['workflow_id']}/orchestration/next",
        json=payload,
    )

    assert prepared.status_code == 200
    decision = prepared.json()
    assert decision["status"] == "READY"
    assert decision["target_agent"] == "discovery"
    assert decision["run_request"]["context"]["repository_boundary"] is None
    assert decision["run_request"]["trace_id"] == "trace-orchestration-discovery"

    replay = client.post(
        f"/v1/workflows/{workflow['workflow_id']}/orchestration/next",
        json=payload,
    )
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True


def test_orchestration_stops_at_specification_human_gate() -> None:
    workflow = client.post(
        "/v1/workflows",
        json={
            "name": "Approval gate slice",
            "client_request": "Build a controlled human approval gate demonstration.",
        },
    ).json()
    workflow_id = workflow["workflow_id"]
    client.post(
        f"/v1/workflows/{workflow_id}/transitions",
        json={
            "action": "start_discovery",
            "actor": "manager",
            "idempotency_key": f"{workflow_id}-start",
        },
    )
    client.post(
        f"/v1/workflows/{workflow_id}/transitions",
        json={
            "action": "submit_specification",
            "actor": "discovery",
            "idempotency_key": f"{workflow_id}-submit",
        },
    )

    response = client.post(
        f"/v1/workflows/{workflow_id}/orchestration/next",
        json={"idempotency_key": f"{workflow_id}-gate-check"},
    )

    assert response.status_code == 200
    decision = response.json()
    assert decision["status"] == "WAITING_FOR_HUMAN"
    assert decision["required_gate"] == "SPECIFICATION_APPROVAL"
    assert decision["target_agent"] is None
    assert decision["run_request"] is None


def test_agent_result_endpoint_rejects_gate_bypass() -> None:
    workflow = client.post(
        "/v1/workflows",
        json={
            "name": "Handoff validation slice",
            "client_request": "Build a controlled handoff validation demonstration.",
        },
    ).json()
    workflow_id = workflow["workflow_id"]
    client.post(
        f"/v1/workflows/{workflow_id}/transitions",
        json={
            "action": "start_discovery",
            "actor": "manager",
            "idempotency_key": f"{workflow_id}-start",
        },
    )

    response = client.post(
        f"/v1/workflows/{workflow_id}/agent-runs/validate",
        json={
            "workflow_id": workflow_id,
            "agent": "discovery",
            "status": "COMPLETED",
            "output_artifact_ids": [],
            "trace_id": "trace-gate-bypass",
            "handoff": {
                "workflow_id": workflow_id,
                "from_agent": "discovery",
                "requested_next_agent": "planner",
                "output_artifact_ids": [],
                "required_gate": "NONE",
                "status": "COMPLETED",
                "trace_id": "trace-gate-bypass",
                "idempotency_key": f"{workflow_id}-invalid-handoff",
            },
        },
    )

    assert response.status_code == 409
    assert "specification approval" in response.json()["detail"]

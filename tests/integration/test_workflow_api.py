"""Workflow endpoint tests (Day 7, spec §18) — through the real API/DI path, proving
`WorkflowEvent` rows logged mid-graph land in the same DB `GET .../workflow/events` reads
(the session-factory fix in DAY7_UNDERSTANDING.md decision 6).
"""
from __future__ import annotations


def _create_project(client) -> str:
    response = client.post("/projects", json={"name": "Leave Management"})
    return response.json()["project_id"]


def test_start_workflow_creates_a_run_and_stub_stops_with_error(client):
    project_id = _create_project(client)

    response = client.post(f"/projects/{project_id}/workflow/start")

    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == project_id
    assert body["workflow_run_id"].startswith("RUN-")
    # No documents/requirements exist yet, so the run reaches the requirement_analyst
    # stub (Day 9 not built) and controlled-stops.
    assert body["status"] == "ERROR"


def test_workflow_status_reflects_the_latest_run(client):
    project_id = _create_project(client)
    start_response = client.post(f"/projects/{project_id}/workflow/start")

    status_response = client.get(f"/projects/{project_id}/workflow/status")

    assert status_response.status_code == 200
    assert status_response.json()["workflow_run_id"] == start_response.json()["workflow_run_id"]
    assert status_response.json()["status"] == "ERROR"


def test_workflow_events_include_supervisor_and_stub_error(client):
    project_id = _create_project(client)
    client.post(f"/projects/{project_id}/workflow/start")

    events_response = client.get(f"/projects/{project_id}/workflow/events")

    assert events_response.status_code == 200
    events = events_response.json()
    actions = [e["action"] for e in events]
    assert "EVALUATE_STATE" in actions
    assert "NOT_IMPLEMENTED" in actions
    assert "STOP_WITH_ERROR" in actions
    error_event = next(e for e in events if e["action"] == "NOT_IMPLEMENTED")
    assert "RequirementAnalyst" in error_event["error"]


def test_status_for_unknown_project_returns_404(client):
    response = client.get("/projects/does-not-exist/workflow/status")
    assert response.status_code == 404


def test_start_for_unknown_project_returns_404(client):
    response = client.post("/projects/does-not-exist/workflow/start")
    assert response.status_code == 404


def test_workflow_supervisor_makes_routing_decision(client):
    """Supervisor Agent runs and makes a routing decision."""
    project_id = _create_project(client)
    client.post(f"/projects/{project_id}/workflow/start")

    events_response = client.get(f"/projects/{project_id}/workflow/events")
    events = events_response.json()

    # Supervisor should have logged a RECOMMEND_* action (its decision)
    supervisor_events = [e for e in events if e["agent"] == "Supervisor"]
    assert len(supervisor_events) >= 2, "Supervisor should log EVALUATE_STATE and RECOMMEND_*"

    # Check for the decision action (should recommend RUN_REQUIREMENT_ANALYST when empty)
    decision_events = [e for e in supervisor_events if e["action"].startswith("RECOMMEND_")]
    assert len(decision_events) > 0, "Supervisor should emit a RECOMMEND_* decision"
    assert decision_events[0]["action"] == "RECOMMEND_RUN_REQUIREMENT_ANALYST", \
        "Empty state should recommend requirement analyst"

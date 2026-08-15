"""Workflow endpoint tests (Day 7, spec §18) — through the real API/DI path, proving
`WorkflowEvent` rows logged mid-graph land in the same DB `GET .../workflow/events` reads
(the session-factory fix in DAY7_UNDERSTANDING.md decision 6).

Day 9 made `requirement_analyst` a real agent (live Ollama + Qdrant), not a stub, so a
fresh project with no uploaded documents may legitimately end up either stopped with an
error (nothing extractable, §12.6/§20.1) or waiting at the clarification gate (it found
something). Tests here assert on that structural guarantee rather than a fixed stub outcome.
"""
from __future__ import annotations

from unittest.mock import patch

import httpx

from app.models.workflow import WorkflowRun
from app.workflow.engine import STATUS_WAITING_FOR_HUMAN_INPUT
from app.workflow.graph import compile_graph


def _create_project(client) -> str:
    response = client.post("/projects", json={"name": "Leave Management"})
    return response.json()["project_id"]


def test_start_workflow_creates_a_run_and_terminates(client):
    project_id = _create_project(client)

    response = client.post(f"/projects/{project_id}/workflow/start")

    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == project_id
    assert body["workflow_run_id"].startswith("RUN-")
    # No documents exist yet, so the run either controlled-stops (nothing extractable)
    # or waits for human clarification input — never left "RUNNING" (no infinite loop).
    assert body["status"] in ("ERROR", "WAITING_FOR_HUMAN_INPUT")


def test_workflow_status_reflects_the_latest_run(client):
    project_id = _create_project(client)
    start_response = client.post(f"/projects/{project_id}/workflow/start")

    status_response = client.get(f"/projects/{project_id}/workflow/status")

    assert status_response.status_code == 200
    assert status_response.json()["workflow_run_id"] == start_response.json()["workflow_run_id"]
    assert status_response.json()["status"] == start_response.json()["status"]


def test_workflow_events_include_supervisor_and_requirement_analyst(client):
    project_id = _create_project(client)
    client.post(f"/projects/{project_id}/workflow/start")

    events_response = client.get(f"/projects/{project_id}/workflow/events")

    assert events_response.status_code == 200
    events = events_response.json()
    actions = [e["action"] for e in events]
    assert "EVALUATE_STATE" in actions  # supervisor
    assert "EXTRACT_REQUIREMENTS" in actions  # real requirement_analyst node ran


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


def test_start_workflow_rejects_a_second_run_while_one_is_active(client):
    """A project can only have one workflow run driving it at a time — starting a second
    run while one is RUNNING or WAITING_FOR_HUMAN_INPUT would spawn a concurrent graph
    invocation racing the first one for the same project's rows (and the same local LLM).
    """
    project_id = _create_project(client)
    session = client.session_factory()
    session.add(WorkflowRun(workflow_run_id="RUN-existing", project_id=project_id, status="RUNNING"))
    session.commit()
    session.close()

    response = client.post(f"/projects/{project_id}/workflow/start")

    assert response.status_code == 409


def test_start_workflow_rejects_a_second_run_while_waiting_for_human_input(client):
    project_id = _create_project(client)
    session = client.session_factory()
    session.add(
        WorkflowRun(
            workflow_run_id="RUN-existing", project_id=project_id,
            status="WAITING_FOR_HUMAN_INPUT",
        )
    )
    session.commit()
    session.close()

    response = client.post(f"/projects/{project_id}/workflow/start")

    assert response.status_code == 409


def test_events_only_include_the_latest_run_not_older_finished_runs(client):
    """A project re-run after an earlier failed/finished run must not show that old run's
    events mixed into the current run's execution log (§16.4) — otherwise a healthy new run
    looks like it's stuck repeating old errors.
    """
    from app.models.workflow import WorkflowEvent

    project_id = _create_project(client)
    session = client.session_factory()
    session.add(WorkflowRun(workflow_run_id="RUN-old", project_id=project_id, status="ERROR"))
    session.add(
        WorkflowEvent(
            workflow_run_id="RUN-old", project_id=project_id,
            agent="RequirementAnalyst", action="ERROR", status="ERROR",
        )
    )
    session.commit()
    session.close()

    client.post(f"/projects/{project_id}/workflow/start")
    events = client.get(f"/projects/{project_id}/workflow/events").json()

    assert all(e["workflow_run_id"] != "RUN-old" for e in events)


def test_start_workflow_allows_a_new_run_once_the_previous_one_finished(client):
    project_id = _create_project(client)
    session = client.session_factory()
    session.add(WorkflowRun(workflow_run_id="RUN-old", project_id=project_id, status="COMPLETED"))
    session.commit()
    session.close()

    response = client.post(f"/projects/{project_id}/workflow/start")

    assert response.status_code == 200


def test_abandon_marks_a_running_run_as_error(client):
    """A run whose owning process died mid-flight stays frozen at RUNNING forever — nothing
    resumes it automatically (see docs/superpowers — no startup hook, no side-effecting
    status read ever calls graph.invoke again). This is the human's deliberate way out,
    matching the project's "no auto-approval" pattern: nothing resolves this on its own.
    """
    project_id = _create_project(client)
    session = client.session_factory()
    session.add(WorkflowRun(workflow_run_id="RUN-stuck", project_id=project_id, status="RUNNING"))
    session.commit()
    session.close()

    response = client.post(f"/projects/{project_id}/workflow/abandon")

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_run_id"] == "RUN-stuck"
    assert body["status"] == "ERROR"


def test_abandon_marks_a_waiting_for_human_input_run_as_error(client):
    project_id = _create_project(client)
    session = client.session_factory()
    session.add(
        WorkflowRun(
            workflow_run_id="RUN-stuck", project_id=project_id,
            status=STATUS_WAITING_FOR_HUMAN_INPUT,
        )
    )
    session.commit()
    session.close()

    response = client.post(f"/projects/{project_id}/workflow/abandon")

    assert response.status_code == 200
    assert response.json()["status"] == "ERROR"


def test_abandon_sets_ended_at(client):
    project_id = _create_project(client)
    session = client.session_factory()
    session.add(WorkflowRun(workflow_run_id="RUN-stuck", project_id=project_id, status="RUNNING"))
    session.commit()
    session.close()

    response = client.post(f"/projects/{project_id}/workflow/abandon")

    assert response.json()["ended_at"] is not None


def test_abandon_logs_an_event(client):
    project_id = _create_project(client)
    session = client.session_factory()
    session.add(WorkflowRun(workflow_run_id="RUN-stuck", project_id=project_id, status="RUNNING"))
    session.commit()
    session.close()

    client.post(f"/projects/{project_id}/workflow/abandon")
    events = client.get(f"/projects/{project_id}/workflow/events").json()

    assert any(e["action"] == "ABANDONED" and e["status"] == "ERROR" for e in events)


def test_abandon_returns_409_when_run_is_already_completed(client):
    project_id = _create_project(client)
    session = client.session_factory()
    session.add(WorkflowRun(workflow_run_id="RUN-done", project_id=project_id, status="COMPLETED"))
    session.commit()
    session.close()

    response = client.post(f"/projects/{project_id}/workflow/abandon")

    assert response.status_code == 409


def test_abandon_returns_404_when_no_run_exists(client):
    project_id = _create_project(client)

    response = client.post(f"/projects/{project_id}/workflow/abandon")

    assert response.status_code == 404


def test_abandon_returns_404_for_unknown_project(client):
    response = client.post("/projects/does-not-exist/workflow/abandon")
    assert response.status_code == 404


def test_abandon_unblocks_starting_a_new_run(client):
    """The actual problem this fixes: a stuck run's frozen RUNNING status permanently
    blocks /workflow/start's conflict check (see
    test_start_workflow_rejects_a_second_run_while_one_is_active) — abandon() is the only
    way out of that once nothing is left to legitimately finish the old run.
    """
    project_id = _create_project(client)
    session = client.session_factory()
    session.add(WorkflowRun(workflow_run_id="RUN-stuck", project_id=project_id, status="RUNNING"))
    session.commit()
    session.close()

    abandon_response = client.post(f"/projects/{project_id}/workflow/abandon")
    assert abandon_response.status_code == 200

    start_response = client.post(f"/projects/{project_id}/workflow/start")

    assert start_response.status_code == 200


def test_status_pending_gate_is_null_when_not_waiting(client):
    project_id = _create_project(client)
    session = client.session_factory()
    session.add(WorkflowRun(workflow_run_id="RUN-running", project_id=project_id, status="RUNNING"))
    session.commit()
    session.close()

    response = client.get(f"/projects/{project_id}/workflow/status")

    assert response.status_code == 200
    assert response.json()["pending_gate"] is None


def test_status_pending_gate_reflects_the_actual_interrupted_gate(client):
    """`pending_gate` must come from the interrupt's own payload (which gate actually called
    `interrupt()`), not be guessed from `WorkflowRun.status` — that status alone can't tell
    the clarification gate and the final gate apart. This is the same deterministic signal
    the approve endpoints use to guard against resuming the wrong gate (see
    test_approve_clarifications_while_paused_at_final_gate_returns_409).
    """
    project_id = _create_project(client)
    session_factory = client.session_factory

    workflow_run_id = "RUN-pending-gate-test"
    config = {
        "configurable": {
            "thread_id": workflow_run_id,
            "session_factory": session_factory,
            "vector_service": None,
        },
        "recursion_limit": 20,
    }
    graph = compile_graph(client.checkpointer)
    seeded_state = {
        "project_id": project_id,
        "current_stage": "start",
        "next_action": None,
        "document_ids": [],
        "requirement_ids": ["REQ-1"],
        "unresolved_question_ids": [],
        "requirement_analysis_attempts": 1,
        "clarification_approved": True,
        "plan_version_id": "ver_1",
        "reviewer_decision": "PASS",
        "reviewer_issue_ids": [],
        "revision_count": 0,
        "final_approved": False,
        "errors": [],
        "workflow_events": [],
    }
    interrupted = graph.invoke(seeded_state, config=config)
    assert interrupted["__interrupt__"][0].value["stage"] == "final_gate"

    session = session_factory()
    try:
        session.add(
            WorkflowRun(
                workflow_run_id=workflow_run_id,
                project_id=project_id,
                status=STATUS_WAITING_FOR_HUMAN_INPUT,
            )
        )
        session.commit()
    finally:
        session.close()

    response = client.get(f"/projects/{project_id}/workflow/status")

    assert response.status_code == 200
    assert response.json()["pending_gate"] == "final_gate"


def test_start_workflow_with_ollama_down_returns_clean_error_status_not_a_crash(client):
    """§25 'Ollama unavailable' at the full API level: the endpoint itself must return 200
    with a WorkflowRun body whose status is ERROR — not a 500 (a generic catch-all would
    otherwise mask a real regression in this path as "just some unexpected error").
    """
    project_id = _create_project(client)

    with patch("ollama.generate", side_effect=httpx.ConnectError("Connection refused")):
        response = client.post(f"/projects/{project_id}/workflow/start")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ERROR"

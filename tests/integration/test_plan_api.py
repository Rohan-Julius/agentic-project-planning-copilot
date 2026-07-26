"""Plan read + approval endpoint tests (Day 12/14, spec §9.7, §11 approval point 2, §18)."""
from __future__ import annotations

from app.database.session import get_sessionmaker
from app.models.workflow import WorkflowRun
from app.schemas.planning import ProjectPlan, ProjectSummary, Scope
from app.tools.project_tools import save_planning_artifacts
from app.workflow.engine import STATUS_WAITING_FOR_HUMAN_INPUT
from app.workflow.graph import compile_graph


def _create_project(client) -> str:
    response = client.post("/projects", json={"name": "Leave Management"})
    return response.json()["project_id"]


def _minimal_plan() -> ProjectPlan:
    return ProjectPlan(
        summary=ProjectSummary(business_problem="X", proposed_solution="Y"),
        scope=Scope(in_scope=["A"]),
    )


def test_get_plan_before_generation_returns_404(client):
    project_id = _create_project(client)

    response = client.get(f"/projects/{project_id}/plan")

    assert response.status_code == 404


def test_get_plan_returns_saved_plan(client):
    project_id = _create_project(client)
    session_factory = client.app.dependency_overrides[get_sessionmaker]()
    save_planning_artifacts(project_id, _minimal_plan(), session_factory=session_factory)

    response = client.get(f"/projects/{project_id}/plan")

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["business_problem"] == "X"
    assert body["scope"]["in_scope"] == ["A"]


def test_get_plan_for_unknown_project_returns_404(client):
    response = client.get("/projects/does-not-exist/plan")
    assert response.status_code == 404


def test_get_plan_is_project_isolated(client):
    project_a = _create_project(client)
    project_b = _create_project(client)
    session_factory = client.app.dependency_overrides[get_sessionmaker]()
    save_planning_artifacts(project_a, _minimal_plan(), session_factory=session_factory)

    response = client.get(f"/projects/{project_b}/plan")

    assert response.status_code == 404


def test_plan_approve_with_no_workflow_run_returns_404(client):
    project_id = _create_project(client)

    response = client.post(f"/projects/{project_id}/plan/approve")

    assert response.status_code == 404


def test_plan_approve_when_not_waiting_returns_409(client):
    project_id = _create_project(client)
    session_factory = client.app.dependency_overrides[get_sessionmaker]()
    session = session_factory()
    try:
        session.add(WorkflowRun(workflow_run_id="RUN-not-waiting", project_id=project_id, status="RUNNING"))
        session.commit()
    finally:
        session.close()

    response = client.post(f"/projects/{project_id}/plan/approve")

    assert response.status_code == 409


def test_plan_approve_releases_the_final_gate_and_reaches_export(client):
    project_id = _create_project(client)
    session_factory = client.app.dependency_overrides[get_sessionmaker]()

    # Drive a compiled graph directly to the final gate under a known thread_id, bypassing
    # the live-LLM planning/reviewer nodes — this test is about the approve endpoint's own
    # wiring (finds the run, patches state, resumes), matching how
    # test_approve_releases_the_clarification_gate proves the same thing for gate 1.
    workflow_run_id = "RUN-final-approve-test"
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
    assert "__interrupt__" in interrupted
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

    response = client.post(f"/projects/{project_id}/plan/approve")

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_run_id"] == workflow_run_id
    assert body["final_approved"] is True
    assert body["status"] == "COMPLETED"

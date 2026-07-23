"""Clarification workflow endpoint tests (Day 10, spec §11, §13.2, §18)."""
from __future__ import annotations

from app.database.session import get_sessionmaker
from app.models.requirement import ClarificationQuestionRecord
from app.models.workflow import WorkflowRun
from app.workflow.engine import STATUS_WAITING_FOR_HUMAN_INPUT
from app.workflow.graph import compile_graph


def _create_project(client) -> str:
    response = client.post("/projects", json={"name": "Leave Management"})
    return response.json()["project_id"]


def _seed_question(client, project_id, question_id="CQ-1", status="PENDING") -> None:
    session_factory = client.app.dependency_overrides[get_sessionmaker]()
    session = session_factory()
    try:
        session.add(
            ClarificationQuestionRecord(
                question_id=question_id,
                project_id=project_id,
                category="authentication",
                priority="High",
                status=status,
                payload_json={
                    "question_id": question_id,
                    "category": "authentication",
                    "question": "Which identity providers must be supported?",
                    "reason_for_asking": "Authentication is mentioned but providers are unspecified.",
                    "related_requirement_id": None,
                    "source_reference": None,
                    "priority": "High",
                    "status": status,
                    "user_answer": None,
                },
            )
        )
        session.commit()
    finally:
        session.close()


def test_list_clarifications_returns_seeded_question(client):
    project_id = _create_project(client)
    _seed_question(client, project_id)

    response = client.get(f"/projects/{project_id}/clarifications")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["question_id"] == "CQ-1"
    assert body[0]["status"] == "PENDING"


def test_list_clarifications_is_project_isolated(client):
    project_a = _create_project(client)
    project_b = _create_project(client)
    _seed_question(client, project_a, question_id="CQ-A")
    _seed_question(client, project_b, question_id="CQ-B")

    response = client.get(f"/projects/{project_a}/clarifications")

    body = response.json()
    assert [q["question_id"] for q in body] == ["CQ-A"]


def test_list_clarifications_for_unknown_project_returns_404(client):
    response = client.get("/projects/does-not-exist/clarifications")
    assert response.status_code == 404


def test_submit_answer_updates_status_and_answer(client):
    project_id = _create_project(client)
    _seed_question(client, project_id)

    response = client.post(
        f"/projects/{project_id}/clarifications/answers",
        json=[{"question_id": "CQ-1", "status": "ANSWERED", "user_answer": "Okta and Google Workspace."}],
    )

    assert response.status_code == 200
    listed = client.get(f"/projects/{project_id}/clarifications").json()
    assert listed[0]["status"] == "ANSWERED"
    assert listed[0]["user_answer"] == "Okta and Google Workspace."


def test_submit_answer_can_defer_and_edit_the_question_text(client):
    project_id = _create_project(client)
    _seed_question(client, project_id)

    response = client.post(
        f"/projects/{project_id}/clarifications/answers",
        json=[{
            "question_id": "CQ-1",
            "status": "DEFERRED",
            "question": "Which SSO providers (if any) must be supported at launch?",
        }],
    )

    assert response.status_code == 200
    listed = client.get(f"/projects/{project_id}/clarifications").json()
    assert listed[0]["status"] == "DEFERRED"
    assert listed[0]["question"] == "Which SSO providers (if any) must be supported at launch?"


def test_submit_answer_for_unknown_question_returns_404(client):
    project_id = _create_project(client)

    response = client.post(
        f"/projects/{project_id}/clarifications/answers",
        json=[{"question_id": "CQ-does-not-exist", "status": "ANSWERED", "user_answer": "N/A"}],
    )

    assert response.status_code == 404


def test_approve_with_no_workflow_run_returns_404(client):
    project_id = _create_project(client)

    response = client.post(f"/projects/{project_id}/clarifications/approve")

    assert response.status_code == 404


def test_approve_when_not_waiting_returns_409(client):
    project_id = _create_project(client)
    session_factory = client.app.dependency_overrides[get_sessionmaker]()
    session = session_factory()
    try:
        session.add(
            WorkflowRun(workflow_run_id="RUN-not-waiting", project_id=project_id, status="RUNNING")
        )
        session.commit()
    finally:
        session.close()

    response = client.post(f"/projects/{project_id}/clarifications/approve")

    assert response.status_code == 409


def test_approve_releases_the_clarification_gate(client):
    project_id = _create_project(client)
    _seed_question(client, project_id, question_id="CQ-1")

    session_factory = client.app.dependency_overrides[get_sessionmaker]()

    # Drive a compiled graph to the clarification gate directly under a known thread_id,
    # bypassing the live-LLM requirement_analyst node — this test is about the approve
    # endpoint's wiring (finds the run, patches state, resumes), not requirement extraction.
    workflow_run_id = "RUN-approve-test"
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
        "unresolved_question_ids": ["CQ-1"],
        "requirement_analysis_attempts": 1,
        "clarification_approved": False,
        "plan_version_id": None,
        "reviewer_decision": None,
        "reviewer_issue_ids": [],
        "revision_count": 0,
        "final_approved": False,
        "errors": [],
        "workflow_events": [],
    }
    interrupted = graph.invoke(seeded_state, config=config)
    assert "__interrupt__" in interrupted

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

    response = client.post(f"/projects/{project_id}/clarifications/approve")

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_run_id"] == workflow_run_id
    # Gate released -> routed to the still-stubbed planning node (Day 11) -> controlled stop.
    assert body["status"] == "ERROR"

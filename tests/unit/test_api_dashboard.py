"""Dashboard endpoint tests (spec §16.1, §18) — one aggregate row per project, every
field mechanically derived from data other services already own (no new business logic,
no agent involvement).
"""
from __future__ import annotations

from app.models.document import DocumentRecord
from app.models.plan_artifact import PlanArtifactVersion
from app.models.requirement import ClarificationQuestionRecord, RequirementRecord
from app.models.workflow import WorkflowRun


def _create_project(client, name: str = "Leave Management") -> str:
    resp = client.post("/projects", json={"name": name})
    return resp.json()["project_id"]


def test_dashboard_empty_when_no_projects(client):
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert resp.json() == []


def test_dashboard_row_defaults_for_a_fresh_project(client):
    project_id = _create_project(client)

    resp = client.get("/dashboard")

    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["project_id"] == project_id
    assert row["name"] == "Leave Management"
    assert row["status"] == "CREATED"
    assert row["document_count"] == 0
    assert row["requirement_analysis_status"] == "NOT_STARTED"
    assert row["clarification_status"] == "NOT_STARTED"
    assert row["planning_status"] == "NOT_STARTED"
    assert row["reviewer_status"] == "NOT_STARTED"
    assert row["approval_status"] == "NOT_APPROVED"


def test_dashboard_reflects_document_count(client):
    project_id = _create_project(client)
    with client.session_factory() as session:
        session.add(
            DocumentRecord(
                document_id="doc_1", project_id=project_id, document_name="reqs.pdf",
                file_path="/tmp/reqs.pdf",
            )
        )
        session.commit()

    row = client.get("/dashboard").json()[0]

    assert row["document_count"] == 1


def test_dashboard_requirement_analysis_in_progress_before_requirements_extracted(client):
    project_id = _create_project(client)
    with client.session_factory() as session:
        session.add(WorkflowRun(workflow_run_id="RUN-1", project_id=project_id))
        session.commit()

    row = client.get("/dashboard").json()[0]

    assert row["requirement_analysis_status"] == "IN_PROGRESS"


def test_dashboard_requirement_analysis_complete_once_requirements_exist(client):
    project_id = _create_project(client)
    with client.session_factory() as session:
        session.add(
            RequirementRecord(
                requirement_id="REQ-001", project_id=project_id, title="Submit leave",
                category="functional", classification="SOURCE_BACKED", payload_json={},
            )
        )
        session.commit()

    row = client.get("/dashboard").json()[0]

    assert row["requirement_analysis_status"] == "COMPLETE"


def test_dashboard_clarification_pending_review_then_resolved(client):
    project_id = _create_project(client)
    with client.session_factory() as session:
        session.add(
            ClarificationQuestionRecord(
                question_id="Q-001", project_id=project_id, status="PENDING", payload_json={},
            )
        )
        session.commit()

    pending_row = client.get("/dashboard").json()[0]
    assert pending_row["clarification_status"] == "PENDING_REVIEW"

    with client.session_factory() as session:
        record = session.query(ClarificationQuestionRecord).one()
        record.status = "ANSWERED"
        session.commit()

    resolved_row = client.get("/dashboard").json()[0]
    assert resolved_row["clarification_status"] == "RESOLVED"


def test_dashboard_planning_complete_and_reviewer_reflects_decision(client):
    project_id = _create_project(client)
    with client.session_factory() as session:
        session.add(
            PlanArtifactVersion(
                version_id="ver_1", project_id=project_id, version_number=1,
                plan_json={}, is_current=True, reviewer_decision=None,
            )
        )
        session.commit()

    row = client.get("/dashboard").json()[0]
    assert row["planning_status"] == "COMPLETE"
    assert row["reviewer_status"] == "NOT_STARTED"

    with client.session_factory() as session:
        version = session.query(PlanArtifactVersion).one()
        version.reviewer_decision = "PASS_WITH_WARNINGS"
        session.commit()

    row = client.get("/dashboard").json()[0]
    assert row["reviewer_status"] == "PASS_WITH_WARNINGS"


def test_dashboard_approval_status_reflects_final_approved(client):
    project_id = _create_project(client)
    with client.session_factory() as session:
        session.add(
            WorkflowRun(
                workflow_run_id="RUN-1", project_id=project_id, status="COMPLETED",
                final_approved=True,
            )
        )
        session.commit()

    row = client.get("/dashboard").json()[0]

    assert row["approval_status"] == "APPROVED"


def test_dashboard_rows_stay_isolated_per_project(client):
    """§12.3/§20.4: one project's activity must never bleed into another's row."""
    active_id = _create_project(client, "Active Project")
    quiet_id = _create_project(client, "Quiet Project")
    with client.session_factory() as session:
        session.add(
            RequirementRecord(
                requirement_id="REQ-001", project_id=active_id, title="Submit leave",
                category="functional", classification="SOURCE_BACKED", payload_json={},
            )
        )
        session.commit()

    rows_by_id = {row["project_id"]: row for row in client.get("/dashboard").json()}

    assert rows_by_id[active_id]["requirement_analysis_status"] == "COMPLETE"
    assert rows_by_id[quiet_id]["requirement_analysis_status"] == "NOT_STARTED"

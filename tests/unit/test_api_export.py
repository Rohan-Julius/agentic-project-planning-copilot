"""Export endpoint tests (Day 14, spec §16.8, §17, §18, §20.2, §20.5)."""
from __future__ import annotations

import csv
import io
import zipfile

from app.models.plan_artifact import PlanArtifactVersion
from app.models.workflow import WorkflowRun


def _create_project(client) -> str:
    resp = client.post("/projects", json={"name": "Export API Project"})
    return resp.json()["project_id"]


_SAMPLE_PLAN_JSON = {
    "summary": {"business_problem": "Manual leave tracking is slow.", "proposed_solution": "Build a system."},
    "scope": {"in_scope": ["Leave requests"], "out_of_scope": []},
    "epics": [
        {
            "epic_id": "EPIC-001", "title": "Leave requests", "objective": "Let employees request leave",
            "business_value": "Reduces manual tracking", "description": "", "priority": "High",
            "dependencies": [], "risks": [], "classification": "SOURCE_BACKED",
            "source_references": [
                {"document_name": "requirements.pdf", "page_number": 2, "section": "Leave", "chunk_id": "DOC-1-CH-001"}
            ],
        }
    ],
    "stories": [
        {
            "story_id": "US-001", "epic_id": "EPIC-001", "title": "Submit leave request",
            "persona": "Employee", "story_statement": "request leave", "business_value": "track time off",
            "priority": "High", "classification": "SOURCE_BACKED",
            "source_references": [
                {"document_name": "requirements.pdf", "page_number": 2, "section": "Leave", "chunk_id": "DOC-1-CH-001"}
            ],
            "acceptance_criteria": [
                {"criterion_id": "AC-001", "given": "an employee is logged in", "when": "they submit a leave request", "then": "the request is recorded"}
            ],
            "dependencies": [], "assumptions": [], "suggested_story_points": 3, "confidence": 0.8,
        }
    ],
    "technical_tasks": [],
    "raid": {"risks": [], "assumptions": [], "issues": [], "dependencies": []},
    "sprint_plan": None,
    "traceability": {"rows": []},
}


def _seed_plan(client, project_id: str) -> None:
    with client.session_factory() as session:
        session.add(
            PlanArtifactVersion(
                version_id="ver_1", project_id=project_id, version_number=1,
                plan_json=_SAMPLE_PLAN_JSON, is_current=True,
            )
        )
        session.commit()


def test_export_endpoints_return_404_for_unknown_project(client):
    for fmt in ("json", "markdown", "jira-csv", "zip", "docx"):
        resp = client.get(f"/projects/PRJ-NOPE/export/{fmt}")
        assert resp.status_code == 404


def test_export_endpoints_return_404_when_no_plan_yet(client):
    project_id = _create_project(client)
    for fmt in ("json", "markdown", "jira-csv", "zip", "docx"):
        resp = client.get(f"/projects/{project_id}/export/{fmt}")
        assert resp.status_code == 404


def test_export_json_labels_unapproved_plan_as_draft(client):
    project_id = _create_project(client)
    _seed_plan(client, project_id)

    resp = client.get(f"/projects/{project_id}/export/json")

    assert resp.status_code == 200
    body = resp.json()
    assert body["export_metadata"]["approval_status"] == "DRAFT_PENDING_APPROVAL"
    assert body["plan"]["epics"][0]["epic_id"] == "EPIC-001"


def test_export_json_labels_approved_plan_as_approved(client):
    project_id = _create_project(client)
    _seed_plan(client, project_id)
    with client.session_factory() as session:
        session.add(
            WorkflowRun(workflow_run_id="RUN-1", project_id=project_id, status="COMPLETED", final_approved=True)
        )
        session.commit()

    resp = client.get(f"/projects/{project_id}/export/json")

    assert resp.status_code == 200
    assert resp.json()["export_metadata"]["approval_status"] == "APPROVED"


def test_export_markdown_flow(client):
    project_id = _create_project(client)
    _seed_plan(client, project_id)

    resp = client.get(f"/projects/{project_id}/export/markdown")

    assert resp.status_code == 200
    assert "EPIC-001: Leave requests" in resp.text


def test_export_jira_csv_flow(client):
    project_id = _create_project(client)
    _seed_plan(client, project_id)

    resp = client.get(f"/projects/{project_id}/export/jira-csv")

    assert resp.status_code == 200
    reader = csv.DictReader(io.StringIO(resp.text))
    rows = list(reader)
    assert len(rows) == 2
    assert rows[0]["Issue Type"] == "Epic"
    assert rows[1]["Issue Type"] == "Story"


def test_export_docx_flow(client):
    from docx import Document

    project_id = _create_project(client)
    _seed_plan(client, project_id)

    resp = client.get(f"/projects/{project_id}/export/docx")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    doc = Document(io.BytesIO(resp.content))
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "Leave requests" in full_text


def test_export_zip_bundles_json_markdown_csv_and_docx(client):
    project_id = _create_project(client)
    _seed_plan(client, project_id)

    resp = client.get(f"/projects/{project_id}/export/zip")

    assert resp.status_code == 200
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        names = set(zf.namelist())
    assert names == {"plan.json", "plan.md", "jira.csv", "plan.docx"}

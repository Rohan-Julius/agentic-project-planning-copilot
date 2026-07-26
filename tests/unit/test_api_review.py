"""API tests for GET /projects/{id}/review (spec §13.12, §18)."""
from __future__ import annotations

from app.models import PlanArtifactVersion


def test_get_review_returns_404_for_unknown_project(client):
    resp = client.get("/projects/PRJ-NOPE/review")
    assert resp.status_code == 404


def test_get_review_returns_404_when_no_review_yet(client):
    create_resp = client.post("/projects", json={"name": "Review API Project"})
    project_id = create_resp.json()["project_id"]

    resp = client.get(f"/projects/{project_id}/review")

    assert resp.status_code == 404
    assert "No review generated" in resp.json()["detail"]


def test_get_review_returns_persisted_report(client):
    create_resp = client.post("/projects", json={"name": "Review API Project 2"})
    project_id = create_resp.json()["project_id"]

    with client.session_factory() as session:
        session.add(
            PlanArtifactVersion(
                version_id="ver_1", project_id=project_id, version_number=1, plan_json={},
                is_current=True, reviewer_decision="PASS_WITH_WARNINGS",
                reviewer_report_json={
                    "decision": "PASS_WITH_WARNINGS",
                    "missing_requirements": [], "unsupported_claims": [], "duplicate_stories": [],
                    "missing_acceptance_criteria": [], "weak_acceptance_criteria": [],
                    "traceability_gaps": [], "dependency_issues": [],
                    "warnings": ["Story US-001 could be split."], "revision_instructions": [],
                },
            )
        )
        session.commit()

    resp = client.get(f"/projects/{project_id}/review")

    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] == "PASS_WITH_WARNINGS"
    assert body["warnings"] == ["Story US-001 could be split."]

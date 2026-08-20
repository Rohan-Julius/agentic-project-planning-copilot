"""Tests for the Day 23 plan-version history endpoints (spec §22)."""
from __future__ import annotations

import uuid


def _create_project(client) -> str:
    resp = client.post("/projects", json={"name": "Versioning Test", "methodology": "agile_scrum"})
    assert resp.status_code == 201
    return resp.json()["project_id"]


def _seed_plan_version(
    client, project_id: str, *, version_number: int, is_current: bool, model="qwen3:4b-instruct",
) -> str:
    from app.models.plan_artifact import PlanArtifactVersion

    version_id = f"ver_{uuid.uuid4().hex[:12]}"
    session = client.session_factory()
    try:
        session.add(
            PlanArtifactVersion(
                version_id=version_id,
                project_id=project_id,
                version_number=version_number,
                plan_json={
                    "summary": {"business_problem": "x", "proposed_solution": "y"},
                    "scope": {},
                    "epics": [], "stories": [], "technical_tasks": [],
                    "raid": {"risks": [], "assumptions": [], "issues": [], "dependencies": []},
                    "sprint_plan": {"suggested_sprint_count": 1, "sprints": [], "unscheduled_story_ids": []},
                    "traceability": {"rows": []},
                },
                model=model,
                prompt_version="planning-v1",
                reviewer_decision="PASS" if is_current else "REVISION_REQUIRED",
                is_current=is_current,
            )
        )
        session.commit()
    finally:
        session.close()
    return version_id


def test_list_plan_versions_returns_all_versions_newest_first(client):
    project_id = _create_project(client)
    _seed_plan_version(client, project_id, version_number=1, is_current=False)
    v2 = _seed_plan_version(client, project_id, version_number=2, is_current=True)

    response = client.get(f"/projects/{project_id}/plan/versions")

    assert response.status_code == 200
    versions = response.json()
    assert [v["version_number"] for v in versions] == [2, 1]
    assert versions[0]["version_id"] == v2
    assert versions[0]["is_current"] is True


def test_get_plan_version_returns_the_full_plan_for_a_specific_version(client):
    project_id = _create_project(client)
    v1 = _seed_plan_version(client, project_id, version_number=1, is_current=False)
    _seed_plan_version(client, project_id, version_number=2, is_current=True)

    response = client.get(f"/projects/{project_id}/plan/versions/{v1}")

    assert response.status_code == 200
    assert response.json()["summary"]["business_problem"] == "x"


def test_get_plan_version_404s_for_an_unknown_version_id(client):
    project_id = _create_project(client)
    _seed_plan_version(client, project_id, version_number=1, is_current=True)

    response = client.get(f"/projects/{project_id}/plan/versions/ver_does_not_exist")

    assert response.status_code == 404


def test_list_plan_versions_404s_for_an_unknown_project(client):
    response = client.get("/projects/proj_does_not_exist/plan/versions")

    assert response.status_code == 404


def test_list_plan_versions_is_project_isolated(client):
    project_a = _create_project(client)
    project_b = _create_project(client)
    _seed_plan_version(client, project_a, version_number=1, is_current=True)

    response = client.get(f"/projects/{project_b}/plan/versions")

    assert response.status_code == 200
    assert response.json() == []

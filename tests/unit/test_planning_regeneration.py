"""Tests for selective artifact regeneration (§32 stretch goal)."""
from __future__ import annotations

from unittest.mock import patch


def _create_project(client) -> str:
    resp = client.post("/projects", json={"name": "Regen Test", "methodology": "agile_scrum"})
    assert resp.status_code == 201
    return resp.json()["project_id"]


def _minimal_plan_json() -> dict:
    return {
        "summary": {"business_problem": "x", "proposed_solution": "y"},
        "scope": {},
        "epics": [
            {
                "epic_id": "EPIC-001", "title": "x", "objective": "x", "business_value": "x",
                "priority": "High", "classification": "AI_RECOMMENDATION",
                "source_references": [], "grounding_requirement_ids": [],
            }
        ],
        "stories": [
            {
                "story_id": "US-001", "epic_id": "EPIC-001", "title": "x", "persona": "x",
                "story_statement": "As a x, I want y, so that z.", "business_value": "x",
                "priority": "High",
                "acceptance_criteria": [{"criterion_id": "AC-001", "given": "a", "when": "b", "then": "c"}],
                "classification": "AI_RECOMMENDATION", "source_references": [],
                "grounding_requirement_ids": [], "confidence": 0.9, "suggested_story_points": 3,
            }
        ],
        "technical_tasks": [],
        "raid": {"risks": [], "assumptions": [], "issues": [], "dependencies": []},
        "sprint_plan": {"suggested_sprint_count": 1, "sprints": [], "unscheduled_story_ids": []},
        "traceability": {"rows": []},
    }


def _seed_plan(client, project_id: str, *, final_approved: bool) -> None:
    import uuid as uuid_module

    from app.models.plan_artifact import PlanArtifactVersion
    from app.models.workflow import WorkflowRun

    session = client.session_factory()
    try:
        session.add(
            PlanArtifactVersion(
                version_id=f"ver_{uuid_module.uuid4().hex[:12]}", project_id=project_id,
                version_number=1, plan_json=_minimal_plan_json(),
                model="test", prompt_version="planning-v1", is_current=True,
            )
        )
        session.add(
            WorkflowRun(
                workflow_run_id=f"RUN-{uuid_module.uuid4().hex[:12]}", project_id=project_id,
                status="WAITING_FOR_HUMAN_INPUT", final_approved=final_approved,
            )
        )
        session.commit()
    finally:
        session.close()


def _fake_sprint_plan():
    from app.schemas.planning import SprintPlan

    return SprintPlan(suggested_sprint_count=1, sprints=[], unscheduled_story_ids=["US-001"])


def _fake_tasks_deps_raid_result():
    from app.schemas.planning import PlanningTasksDepsRaidResult

    return PlanningTasksDepsRaidResult(
        technical_tasks=[], dependencies=[], risks=[], assumptions=[], issues=[],
    )


def test_regenerate_sprint_plan_creates_a_new_version(client):
    project_id = _create_project(client)
    _seed_plan(client, project_id, final_approved=False)

    with patch("app.agents.planning.run_agent", return_value=_fake_sprint_plan()):
        response = client.post(f"/projects/{project_id}/plan/regenerate/sprint-plan")

    assert response.status_code == 200
    assert response.json()["sprint_plan"]["unscheduled_story_ids"] == ["US-001"]
    assert response.json()["epics"][0]["epic_id"] == "EPIC-001"  # unchanged

    versions = client.get(f"/projects/{project_id}/plan/versions").json()
    assert len(versions) == 2
    assert versions[0]["version_number"] == 2


def test_regenerate_sprint_plan_resets_final_approved(client):
    project_id = _create_project(client)
    _seed_plan(client, project_id, final_approved=True)

    with patch("app.agents.planning.run_agent", return_value=_fake_sprint_plan()):
        response = client.post(f"/projects/{project_id}/plan/regenerate/sprint-plan")

    assert response.status_code == 200
    export = client.get(f"/projects/{project_id}/export/json")
    assert export.json()["export_metadata"]["approval_status"] != "APPROVED"


def test_regenerate_tasks_deps_raid_creates_a_new_version(client):
    project_id = _create_project(client)
    _seed_plan(client, project_id, final_approved=False)

    with patch(
        "app.agents.planning.search_company_standards", return_value=[]
    ), patch("app.agents.planning.run_agent", return_value=_fake_tasks_deps_raid_result()):
        response = client.post(f"/projects/{project_id}/plan/regenerate/tasks-deps-raid")

    assert response.status_code == 200
    versions = client.get(f"/projects/{project_id}/plan/versions").json()
    assert len(versions) == 2


def test_regenerate_404s_when_no_plan_exists_yet(client):
    project_id = _create_project(client)

    response = client.post(f"/projects/{project_id}/plan/regenerate/sprint-plan")

    assert response.status_code == 404

"""Plan read endpoint tests (Day 12, spec §9.7, §18)."""
from __future__ import annotations

from app.database.session import get_sessionmaker
from app.schemas.planning import ProjectPlan, ProjectSummary, Scope
from app.tools.project_tools import save_planning_artifacts


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

"""Tests for requirement-change impact analysis (§32 stretch goal) — pure deterministic
lookup, no LLM/mocking needed beyond seeding a plan.
"""
from __future__ import annotations

import uuid


def _create_project(client) -> str:
    resp = client.post("/projects", json={"name": "Impact Test", "methodology": "agile_scrum"})
    assert resp.status_code == 201
    return resp.json()["project_id"]


def _seed_plan_with_traceability(client, project_id: str) -> None:
    from app.models.plan_artifact import PlanArtifactVersion

    plan_json = {
        "summary": {"business_problem": "x", "proposed_solution": "y"},
        "scope": {},
        "epics": [
            {
                "epic_id": "EPIC-001", "title": "Payments", "objective": "x", "business_value": "x",
                "priority": "High", "classification": "AI_RECOMMENDATION",
                "source_references": [], "grounding_requirement_ids": ["REQ-1"],
            }
        ],
        "stories": [
            {
                "story_id": "US-001", "epic_id": "EPIC-001", "title": "Pay by card", "persona": "x",
                "story_statement": "As a x, I want y, so that z.", "business_value": "x",
                "priority": "High",
                "acceptance_criteria": [{"criterion_id": "AC-001", "given": "a", "when": "b", "then": "c"}],
                "classification": "AI_RECOMMENDATION", "source_references": [],
                "grounding_requirement_ids": ["REQ-1"], "confidence": 0.9, "suggested_story_points": 3,
            }
        ],
        "technical_tasks": [
            {"task_id": "TASK-001", "story_id": "US-001", "category": "Backend", "description": "x"},
            {"task_id": "TASK-002", "story_id": None, "category": "Backend", "description": "unrelated"},
        ],
        "raid": {
            "risks": [], "assumptions": [], "issues": [],
            "dependencies": [
                {
                    "dependency_id": "DEP-001", "blocking_item_id": "EPIC-001",
                    "blocked_item_id": "US-001", "dependency_type": "BLOCKS",
                    "description": "x", "suggested_resolution": "y",
                }
            ],
        },
        "sprint_plan": {"suggested_sprint_count": 1, "sprints": [], "unscheduled_story_ids": []},
        "traceability": {
            "rows": [
                {
                    "requirement_id": "REQ-1", "source_references": [],
                    "epic_id": "EPIC-001", "story_id": "US-001",
                    "acceptance_criterion_ids": ["AC-001"],
                }
            ]
        },
    }
    session = client.session_factory()
    try:
        session.add(
            PlanArtifactVersion(
                version_id=f"ver_{uuid.uuid4().hex[:12]}", project_id=project_id,
                version_number=1, plan_json=plan_json,
                model="test", prompt_version="planning-v1", is_current=True,
            )
        )
        session.commit()
    finally:
        session.close()


def test_requirement_impact_returns_everything_that_traces_back(client):
    project_id = _create_project(client)
    _seed_plan_with_traceability(client, project_id)

    response = client.get(f"/projects/{project_id}/requirements/REQ-1/impact")

    assert response.status_code == 200
    body = response.json()
    assert [e["epic_id"] for e in body["epics"]] == ["EPIC-001"]
    assert [s["story_id"] for s in body["stories"]] == ["US-001"]
    assert [t["task_id"] for t in body["technical_tasks"]] == ["TASK-001"]
    assert [d["dependency_id"] for d in body["dependencies"]] == ["DEP-001"]


def test_requirement_impact_is_empty_for_an_untraced_requirement(client):
    project_id = _create_project(client)
    _seed_plan_with_traceability(client, project_id)

    response = client.get(f"/projects/{project_id}/requirements/REQ-999/impact")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "requirement_id": "REQ-999", "epics": [], "stories": [],
        "technical_tasks": [], "dependencies": [],
    }


def test_requirement_impact_404s_when_no_plan_exists(client):
    project_id = _create_project(client)

    response = client.get(f"/projects/{project_id}/requirements/REQ-1/impact")

    assert response.status_code == 404


def test_requirement_impact_404s_for_unknown_project(client):
    response = client.get("/projects/proj_does_not_exist/requirements/REQ-1/impact")
    assert response.status_code == 404

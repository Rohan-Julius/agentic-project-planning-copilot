"""Tests for Day 23's contradiction/ambiguity persistence + read endpoints (spec §13.1)."""
from __future__ import annotations

from unittest.mock import patch


def _create_project(client) -> str:
    resp = client.post("/projects", json={"name": "Findings Test", "methodology": "agile_scrum"})
    assert resp.status_code == 201
    return resp.json()["project_id"]


def _fake_result_with_findings():
    from app.schemas.requirement import Ambiguity, Contradiction, Requirement, RequirementAnalysisResult

    return RequirementAnalysisResult(
        requirements=[
            Requirement(
                requirement_id="REQ-1", title="x", description="x", category="functional",
                classification="ASSUMPTION", confidence=0.5,
            )
        ],
        actors=[], missing_information=[],
        contradictions=[
            Contradiction(
                contradiction_id="CON-1", description="1 year vs 7 years retention",
                conflicting_requirement_ids=["REQ-1"],
            )
        ],
        ambiguities=[
            Ambiguity(
                ambiguity_id="AMB-1", description="response time undefined", reason="no metric given",
            )
        ],
        clarification_questions=[],
    )


def test_save_analysis_findings_persists_contradictions_and_ambiguities(client):
    from app.tools.project_tools import save_analysis_findings

    project_id = _create_project(client)
    save_analysis_findings(
        project_id, _fake_result_with_findings(), "RUN-1", session_factory=client.session_factory,
    )

    contradictions = client.get(f"/projects/{project_id}/contradictions").json()
    ambiguities = client.get(f"/projects/{project_id}/ambiguities").json()

    assert len(contradictions) == 1
    assert contradictions[0]["contradiction_id"] == "CON-1"
    assert len(ambiguities) == 1
    assert ambiguities[0]["ambiguity_id"] == "AMB-1"


def test_contradictions_endpoint_is_project_isolated(client):
    from app.tools.project_tools import save_analysis_findings

    project_a = _create_project(client)
    project_b = _create_project(client)
    save_analysis_findings(
        project_a, _fake_result_with_findings(), "RUN-1", session_factory=client.session_factory,
    )

    response = client.get(f"/projects/{project_b}/contradictions")

    assert response.status_code == 200
    assert response.json() == []


def test_contradictions_endpoint_404s_for_unknown_project(client):
    response = client.get("/projects/proj_does_not_exist/contradictions")
    assert response.status_code == 404


def test_requirement_analyst_saves_findings_end_to_end(client):
    """Proves the wiring in run_requirement_analyst_agent, not just save_analysis_findings in
    isolation — mirrors tests/unit/test_requirement_analyst_agent.py's existing mocked-LLM
    pattern.
    """
    project_id = _create_project(client)

    with patch(
        "app.agents.requirement_analyst.search_project_documents", return_value=[]
    ), patch(
        "app.agents.requirement_analyst.search_company_standards", return_value=[]
    ), patch(
        "app.agents.requirement_analyst.run_agent", return_value=_fake_result_with_findings()
    ):
        from app.agents.requirement_analyst import run_requirement_analyst_agent

        run_requirement_analyst_agent(
            project_id, "RUN-1", session_factory=client.session_factory,
        )

    assert client.get(f"/projects/{project_id}/contradictions").json()[0]["contradiction_id"] == "CON-1"

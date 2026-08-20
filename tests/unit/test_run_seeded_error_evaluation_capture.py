"""Structural regression test (Day 23): proves the seeded-error evaluation's per-seed capture
never mixes ReviewerIssue dicts and plain strings in one list again — that exact mixing was
the root cause of a real crash during Day 20's live run (see PROJECT_PLAN.md Day 20 section).
Does not invoke a live Reviewer — mocks run_reviewer_agent and validate_project_plan, matching
this project's existing mocked-agent test conventions.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.schemas.reviewer import ReviewerIssue, ReviewerReport


def _baseline_plan() -> dict:
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
                "grounding_requirement_ids": [], "confidence": 0.9,
                "suggested_story_points": 3,
            }
        ],
        "technical_tasks": [],
        "raid": {"risks": [], "assumptions": [], "issues": [], "dependencies": []},
        "sprint_plan": {"suggested_sprint_count": 1, "sprints": [], "unscheduled_story_ids": []},
        "traceability": {"rows": []},
    }


def test_seeded_error_capture_keeps_every_reviewer_issue_field_separate(client):
    from evaluation.scripts import run_seeded_error_evaluation

    project_id = "PRJ-SEEDED-CAPTURE"
    session = client.session_factory()
    try:
        from app.models.project import ProjectRecord

        session.add(ProjectRecord(project_id=project_id, name="Seeded Capture Test", methodology="agile_scrum"))
        session.commit()
    finally:
        session.close()

    fake_report = ReviewerReport(
        decision="REVISION_REQUIRED",
        missing_requirements=["REQ-9 not represented"],
        unsupported_claims=[
            ReviewerIssue(artifact_id="US-001", issue_type="UNSUPPORTED_CLAIM", description="x", recommended_action="y")
        ],
        weak_acceptance_criteria=[
            ReviewerIssue(artifact_id="US-002", issue_type="WEAK_AC", description="x", recommended_action="y")
        ],
        warnings=["Sprint 3 has no stories"],
    )
    fake_validation = MagicMock(errors=[], is_valid=True)

    with patch.object(
        run_seeded_error_evaluation, "SEEDS", [("noop_seed", lambda plan: plan)]
    ), patch("app.agents.reviewer.run_reviewer_agent", return_value=fake_report), patch(
        "app.tools.validation_tools.validate_project_plan", return_value=fake_validation,
    ):
        results = run_seeded_error_evaluation.main(client, _baseline_plan(), project_id)

    assert len(results) == 1
    result = results[0]
    assert result["outcome"] == "reviewer_ran"

    # Every ReviewerIssue-list field is captured separately, as a list of dicts.
    assert result["unsupported_claims"] == [
        {"artifact_id": "US-001", "issue_type": "UNSUPPORTED_CLAIM", "description": "x", "recommended_action": "y"}
    ]
    assert result["weak_acceptance_criteria"][0]["artifact_id"] == "US-002"
    assert result["duplicate_stories"] == []
    assert result["missing_acceptance_criteria"] == []
    assert result["traceability_gaps"] == []
    assert result["dependency_issues"] == []

    # The two string-list fields are plain strings, never merged with the dict fields above.
    assert result["missing_requirements"] == ["REQ-9 not represented"]
    assert result["warnings"] == ["Sprint 3 has no stories"]
    assert all(isinstance(w, str) for w in result["warnings"])

    # validate_project_plan's own structural result is captured directly, not inferred.
    assert result["structural_errors"] == []
    assert result["structural_is_valid"] is True

    # No "issues" key at all for a reviewer_ran outcome — the exact shape that caused Day 20's
    # crash (a dict where a string was assumed) no longer exists.
    assert "issues" not in result

    # write_report() must not crash on this shape (the actual Day 20 bug).
    run_seeded_error_evaluation.write_report(results)

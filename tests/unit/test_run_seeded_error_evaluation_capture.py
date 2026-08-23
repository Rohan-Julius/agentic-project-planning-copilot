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


def test_seeded_error_capture_keeps_every_reviewer_issue_field_separate(client, tmp_path):
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
        # reports_dir=tmp_path, not the real evaluation/reports/ — main() writes its own
        # report internally (write_report(results, reports_dir=reports_dir)), and the default
        # would silently overwrite this repo's real day20_seeded_error_evaluation.{md,json}
        # with this test's mocked "noop_seed" data on every fast-suite run (found live, Day
        # 25 — it happened twice before this parameter existed).
        results = run_seeded_error_evaluation.main(
            client, _baseline_plan(), project_id, reports_dir=tmp_path,
        )

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

    # write_report() must not crash on this shape (the actual Day 20 bug) — already exercised
    # above via main()'s own internal call; just confirm it actually wrote the files.
    assert (tmp_path / "day20_seeded_error_evaluation.md").exists()
    assert (tmp_path / "day20_seeded_error_evaluation.json").exists()


def test_seed_circular_dependency_writes_to_the_real_schema_location():
    """Day 25 bug fix regression: this seed previously wrote to a bogus top-level
    `plan["dependencies"]` key with a lowercase `dependency_type`, which Pydantic silently
    ignored on parse — every prior run using this seed (including Day 20's original) never
    actually injected a circular dependency at all, making "the Reviewer/validator didn't
    catch it" a false conclusion for that seed specifically. Dependencies live under
    `plan["raid"]["dependencies"]` (RaidLog, app/schemas/planning.py) with an uppercase
    DependencyType literal. This proves the fixed seed both places the dependency correctly
    AND that the resulting plan is genuinely caught by the already-existing, already-tested
    deterministic circular-dependency check (app/tools/validation_tools.py) — no live Reviewer
    call needed, since that check is pure Python.
    """
    from app.schemas.planning import ProjectPlan
    from app.tools.validation_tools import _check_circular_dependencies
    from evaluation.scripts.run_seeded_error_evaluation import _seed_circular_dependency

    baseline = _baseline_plan()
    baseline["stories"].append(
        {
            "story_id": "US-002", "epic_id": "EPIC-001", "title": "y", "persona": "x",
            "story_statement": "As a x, I want z, so that w.", "business_value": "x",
            "priority": "High",
            "acceptance_criteria": [{"criterion_id": "AC-002", "given": "a", "when": "b", "then": "c"}],
            "classification": "AI_RECOMMENDATION", "source_references": [],
            "grounding_requirement_ids": [], "confidence": 0.9,
            "suggested_story_points": 2,
        }
    )

    seeded = _seed_circular_dependency(baseline)

    assert "dependencies" not in seeded  # the bogus top-level key is never created
    assert len(seeded["raid"]["dependencies"]) == 2
    assert {d["dependency_type"] for d in seeded["raid"]["dependencies"]} == {"BLOCKS"}

    plan = ProjectPlan.model_validate(seeded)
    issues = _check_circular_dependencies(plan)

    assert any(i.code == "CIRCULAR_DEPENDENCY" for i in issues)

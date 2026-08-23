"""Day 20 reviewer-effectiveness evaluation (spec §24.7): seeds 6 deliberate errors into a
real, previously-valid plan (Task 1's run 1) and measures whether/how the Reviewer Agent (or
the deterministic layers it depends on) catches each one.

Two of the six spec-named categories — story without an epic, missing acceptance criteria —
are rejected by ProjectPlan's own Pydantic validators before a plan containing them can even
be reloaded, so they never reach the Reviewer Agent as a reviewable plan at all. This script
records that as the honest, correct outcome (a caught ValidationError) rather than treating it
as a script failure — it's a *stronger* form of protection than the Reviewer catching it after
the fact, just a different one than the other four categories get.

Also captures each call's wall-clock duration directly (time.perf_counter), same as Day 19's
Supervisor routing evaluation — these are Reviewer-only calls, no Requirement Analyst or
Planning involved, so much cheaper than Task 1's full pipeline runs.
"""
from __future__ import annotations

import copy
import json
import time
import uuid
from pathlib import Path

REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"


def _seed_story_without_epic(plan: dict) -> dict:
    plan = copy.deepcopy(plan)
    plan["stories"][0]["epic_id"] = "EPIC-999-DOES-NOT-EXIST"
    return plan


def _seed_missing_acceptance_criteria(plan: dict) -> dict:
    plan = copy.deepcopy(plan)
    plan["stories"][0]["acceptance_criteria"] = []
    return plan


def _seed_invalid_citation(plan: dict) -> dict:
    plan = copy.deepcopy(plan)
    for story in plan["stories"]:
        if story.get("source_references"):
            story["source_references"][0]["chunk_id"] = "doc_does_not_exist-CH-999"
            break
    return plan


def _seed_duplicate_story(plan: dict) -> dict:
    plan = copy.deepcopy(plan)
    original = plan["stories"][0]
    duplicate = copy.deepcopy(original)
    duplicate["story_id"] = f"{original['story_id']}-DUP"
    duplicate["title"] = original["title"] + " (near-identical duplicate)"
    plan["stories"].append(duplicate)
    return plan


def _seed_unsupported_requirement(plan: dict) -> dict:
    """A claim marked SOURCE_BACKED whose cited chunk is real (non-dangling — passes the
    deterministic validator) but whose actual content doesn't support the claim being made —
    only the Reviewer's own semantic judgement can catch this, nothing deterministic can.
    """
    plan = copy.deepcopy(plan)
    epic = plan["epics"][0]
    epic["objective"] = (
        "The system must process 50,000 payment transactions per second with sub-millisecond "
        "latency across 12 geographic regions simultaneously."
    )
    return plan


def _seed_circular_dependency(plan: dict) -> dict:
    """Day 25 bug fix: this previously wrote to a bogus top-level `plan["dependencies"]` key
    and used a lowercase `"blocks"` dependency_type. Neither matches the real schema —
    `Dependency` objects live under `plan["raid"]["dependencies"]` (see `RaidLog` in
    app/schemas/planning.py), and `DependencyType` is the uppercase literal
    `"BLOCKS"/"REQUIRES"/"RELATES_TO"`. Pydantic silently ignores unknown extra fields by
    default, so this seed was a silent no-op — every live run since Day 20 that used it
    (including this file's own Day 20 baseline and its Day 25 rerun) never actually injected a
    circular dependency into the plan at all, making the "Reviewer/validator didn't catch it"
    conclusion those runs implied false: there was nothing to catch. Found live during the
    Day 25 rerun by noticing `structural_errors: []` despite `_check_circular_dependencies`
    (validation_tools.py) already existing and being wired into `validate_project_plan`.
    """
    plan = copy.deepcopy(plan)
    stories = plan["stories"]
    if len(stories) >= 2:
        a, b = stories[0]["story_id"], stories[1]["story_id"]
        plan["raid"]["dependencies"] = plan["raid"].get("dependencies", []) + [
            {
                "dependency_id": "DEP-CYCLE-1", "blocking_item_id": a, "blocked_item_id": b,
                "dependency_type": "BLOCKS", "description": "seeded", "suggested_resolution": "",
            },
            {
                "dependency_id": "DEP-CYCLE-2", "blocking_item_id": b, "blocked_item_id": a,
                "dependency_type": "BLOCKS", "description": "seeded", "suggested_resolution": "",
            },
        ]
    return plan


SEEDS = [
    ("story_without_epic", _seed_story_without_epic),
    ("missing_acceptance_criteria", _seed_missing_acceptance_criteria),
    ("invalid_citation", _seed_invalid_citation),
    ("duplicate_story", _seed_duplicate_story),
    ("unsupported_requirement", _seed_unsupported_requirement),
    ("circular_dependency", _seed_circular_dependency),
]


def _persist_plan(session_factory, project_id: str, plan_dict: dict) -> None:
    """Writes plan_dict directly as the current PlanArtifactVersion, bypassing
    save_planning_artifacts (which requires an already-Pydantic-valid ProjectPlan instance —
    exactly what several of these seeded variants must NOT be).
    """
    from app.models.plan_artifact import PlanArtifactVersion
    from sqlalchemy import select

    session = session_factory()
    try:
        previous = session.scalars(
            select(PlanArtifactVersion).where(
                PlanArtifactVersion.project_id == project_id,
                PlanArtifactVersion.is_current.is_(True),
            )
        ).all()
        next_version = 1
        for row in previous:
            row.is_current = False
            next_version = max(next_version, row.version_number + 1)
        session.add(
            PlanArtifactVersion(
                version_id=f"ver_{uuid.uuid4().hex[:12]}",
                project_id=project_id,
                version_number=next_version,
                plan_json=plan_dict,
                model="seeded-error-test",
                prompt_version="planning-v1",
                is_current=True,
            )
        )
        session.commit()
    finally:
        session.close()


def main(client, baseline_plan: dict, project_id: str, *, reports_dir: Path = REPORTS_DIR) -> list[dict]:
    from app.agents.reviewer import run_reviewer_agent
    from app.tools.validation_tools import validate_project_plan
    from pydantic import ValidationError

    session_factory = client.session_factory
    results = []
    for name, seed_fn in SEEDS:
        corrupted = seed_fn(baseline_plan)
        _persist_plan(session_factory, project_id, corrupted)
        start = time.perf_counter()
        try:
            report = run_reviewer_agent(
                project_id, f"RUN-seed-{name}", session_factory=session_factory,
            )
            elapsed = round(time.perf_counter() - start, 1)
            # Day 23: capture every ReviewerReport issue-list field under its own real name
            # (never merged into one "issues" list — that exact mixing of ReviewerIssue dicts
            # and plain strings was the root cause of a real Day 20 crash, see write_report's
            # docstring below) plus validate_project_plan's own direct structural-error list,
            # so attribution (deterministic backstop vs. genuine LLM judgement) is confirmed,
            # not inferred (Day 20's backlog ask).
            structural = validate_project_plan(project_id, session_factory=session_factory)
            results.append({
                "seed": name,
                "outcome": "reviewer_ran",
                "decision": report.decision,
                "duration_seconds": elapsed,
                "unsupported_claims": [i.model_dump(mode="json") for i in report.unsupported_claims],
                "duplicate_stories": [i.model_dump(mode="json") for i in report.duplicate_stories],
                "missing_acceptance_criteria": [i.model_dump(mode="json") for i in report.missing_acceptance_criteria],
                "weak_acceptance_criteria": [i.model_dump(mode="json") for i in report.weak_acceptance_criteria],
                "traceability_gaps": [i.model_dump(mode="json") for i in report.traceability_gaps],
                "dependency_issues": [i.model_dump(mode="json") for i in report.dependency_issues],
                "missing_requirements": list(report.missing_requirements),
                "warnings": list(report.warnings),
                "structural_errors": [e.model_dump(mode="json") for e in structural.errors],
                "structural_is_valid": structural.is_valid,
            })
        except ValidationError as exc:
            elapsed = round(time.perf_counter() - start, 1)
            results.append({
                "seed": name,
                "outcome": "schema_rejected_before_review",
                "decision": None,
                "duration_seconds": elapsed,
                "issues": [str(exc)],
            })
        except Exception as exc:  # noqa: BLE001 — recording any other failure mode, not hiding it
            elapsed = round(time.perf_counter() - start, 1)
            results.append({
                "seed": name,
                "outcome": f"unexpected_error: {type(exc).__name__}",
                "decision": None,
                "duration_seconds": elapsed,
                "issues": [str(exc)],
            })

    write_report(results, reports_dir=reports_dir)
    return results


_ISSUE_LIST_FIELDS = [
    "unsupported_claims", "duplicate_stories", "missing_acceptance_criteria",
    "weak_acceptance_criteria", "traceability_gaps", "dependency_issues",
]


def _note_for(r: dict) -> str:
    """Day 23: a single human-readable summary column, built from the correct shape per
    outcome — never assumes `r["issues"]` exists (reviewer_ran results no longer have that
    key at all; schema_rejected/unexpected_error results still do, as a plain string list).
    This replaces the Day 20 bug's exact failure mode (str-slicing a dict as if it were
    always a string) by never mixing the two shapes into one field in the first place.
    """
    if r["outcome"] == "reviewer_ran":
        counts = {field: len(r[field]) for field in _ISSUE_LIST_FIELDS if r[field]}
        structural_note = (
            f"structural_errors={len(r['structural_errors'])}" if r["structural_errors"] else ""
        )
        parts = [f"{field}={count}" for field, count in counts.items()] + (
            [structural_note] if structural_note else []
        )
        return "; ".join(parts)[:150] if parts else "(no issues reported)"
    return str(r["issues"][0])[:150] if r.get("issues") else ""


def write_report(results: list[dict], *, reports_dir: Path = REPORTS_DIR) -> None:
    """Day 25 bug fix: `reports_dir` used to be hardcoded to the real REPORTS_DIR, so every
    call — including from test_run_seeded_error_evaluation_capture.py's own structural test,
    which runs on every `pytest -m "not slow"` invocation — silently overwrote this repo's real
    day20_seeded_error_evaluation.{md,json} with that test's mocked "noop_seed" data. Found
    live: it clobbered this exact day's real seeded-error rerun results twice. Callers writing
    real results (main(), below) use the default; the test now passes tmp_path instead.
    """
    reports_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Day 20 Reviewer Effectiveness — 6 Seeded Errors (spec §24.7)",
        "",
        "| Seed | Outcome | Reviewer decision | Duration (s) | Notes |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['seed']} | {r['outcome']} | {r['decision']} | "
            f"{r['duration_seconds']} | {_note_for(r)} |"
        )
    (reports_dir / "day20_seeded_error_evaluation.md").write_text("\n".join(lines))
    (reports_dir / "day20_seeded_error_evaluation.json").write_text(
        json.dumps(results, indent=2, default=str)
    )

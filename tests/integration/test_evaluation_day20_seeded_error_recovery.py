"""One-off recovery test (not part of the permanent Day 20 suite — see
tests/integration/test_evaluation_day20.py for the real driver): the first live run of
run_seeded_error_evaluation crashed inside its own write_report() (a str-slicing bug on
ReviewerIssue dicts, fixed in evaluation/scripts/run_seeded_error_evaluation.py) *after* all 6
live Reviewer calls had already completed successfully — the computed results were lost with
the process exit (in-memory DB) since the crash happened before write_report's file write.

Re-running the full 3x repeatability evaluation just to get a fresh baseline would needlessly
redo ~2.75 hours of already-good, already-saved work (evaluation/reports/day20_repeatability_
evaluation.md and the 3 run*_plan.json files are untouched by this bug and don't need
regenerating). Reusing the original run 1's saved plan.json against a brand-new project isn't
valid either — its citations point to chunk_ids that only existed in the original (now-gone)
in-memory project, so every citation would appear dangling regardless of the seeded defect,
corrupting the comparison. The only correct fix is one fresh, self-consistent (project, plan,
requirements, chunks) tuple — this test produces exactly one via run_once(), then feeds it
straight into the (now-fixed) seeded-error evaluation in the same process.
"""
from __future__ import annotations

import pytest

from evaluation.scripts import run_repeatability_evaluation, run_seeded_error_evaluation


@pytest.mark.slow
def test_seeded_error_evaluation_recovery_run(client):
    baseline = run_repeatability_evaluation.run_once(client, run_number="seed-baseline")
    assert baseline["final_status"] == "COMPLETED", baseline
    assert baseline["plan"] is not None

    results = run_seeded_error_evaluation.main(client, baseline["plan"], baseline["project_id"])
    assert len(results) == 6
    for r in results:
        assert r["outcome"] in ("reviewer_ran", "schema_rejected_before_review"), r

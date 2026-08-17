"""Day 20 evaluation driver (spec §24.6, §24.7, §24.8) — thin pytest wrapper, same pattern as
Day 19's tests/integration/test_evaluation_day19.py. Actual logic lives in evaluation/scripts/.

Deliberately one test, not two: the seeded-error evaluation (§24.7) reuses run 1's real plan
and project_id from the repeatability evaluation (§24.8) directly, in-process, rather than
re-running the full pipeline a second time just to obtain them again — `client`'s in-memory DB
doesn't survive across separate pytest invocations, so splitting this into two independently
runnable slow tests would silently double the most expensive part of this day.
"""
from __future__ import annotations

import pytest

from evaluation.scripts import run_repeatability_evaluation, run_seeded_error_evaluation


@pytest.mark.slow
def test_run_day20_repeatability_and_seeded_error_evaluation(client):
    repeatability_results = run_repeatability_evaluation.main(client)
    assert len(repeatability_results) == 3
    for r in repeatability_results:
        assert r["final_status"] == "COMPLETED", r
        assert r["plan"] is not None

    run1 = repeatability_results[0]
    seeded_results = run_seeded_error_evaluation.main(client, run1["plan"], run1["project_id"])
    assert len(seeded_results) == 6
    for r in seeded_results:
        assert r["outcome"] in ("reviewer_ran", "schema_rejected_before_review")

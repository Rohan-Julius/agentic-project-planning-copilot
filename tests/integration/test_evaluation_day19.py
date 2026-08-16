"""Day 19 evaluation driver (spec §24.1, §24.2, §24.3, §24.4) — thin pytest wrapper around
the real evaluation/scripts/*.py so the live-model evaluation runs stay part of this
project's normal `pytest -m slow` workflow. The actual evaluation logic and report-writing
live in evaluation/scripts/ (repo structure §26); this file only supplies the existing
fixtures and asserts each run at least completed without crashing — the substantive pass/fail
judgment for routing lives in the written report (day19_routing_evaluation.md), not here.
"""
from __future__ import annotations

import pytest

from evaluation.scripts import run_extraction_evaluation, run_routing_evaluation


@pytest.mark.slow
def test_run_day19_extraction_and_clarification_evaluation(client):
    results = run_extraction_evaluation.main(client)
    assert len(results) == 3
    for result in results:
        assert result["workflow_status"] in ("ERROR", "WAITING_FOR_HUMAN_INPUT")


@pytest.mark.slow
def test_run_day19_routing_evaluation(client):
    results = run_routing_evaluation.main(client.session_factory)
    assert len(results) >= 15
    pass_rate = sum(1 for r in results if r["passed"]) / len(results)
    assert pass_rate >= 0.7, f"Supervisor routing pass rate too low: {pass_rate:.0%}"

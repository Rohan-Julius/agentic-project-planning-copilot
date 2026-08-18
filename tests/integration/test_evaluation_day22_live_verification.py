"""Day 22 live verification driver. Marked slow — a single run against the real qwen3:4b
model takes on the order of 1-2 hours (Requirement Analyst + 4 sequential Planning calls +
Reviewer, possibly one revision cycle). Run explicitly with `pytest -m slow`.
"""
from __future__ import annotations

import pytest

from evaluation.scripts import run_day22_live_verification


@pytest.mark.slow
def test_run_day22_live_verification(client):
    result = run_day22_live_verification.main(client)
    assert result["final_status"] in ("COMPLETED", "WAITING_FOR_HUMAN_INPUT")
    assert result["duration_ms_populated"] is True

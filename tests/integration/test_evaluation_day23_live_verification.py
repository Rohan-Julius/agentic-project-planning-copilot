"""Day 23 live verification: reruns Day 22's scenario-1 full-pipeline script (unchanged —
it's scenario-agnostic despite the filename) to confirm Task 1 (dependency descriptions) and
Task 4 (contradictions/ambiguities persistence) behaviorally, on top of reconfirming Day 22's
fixes still hold. Marked slow — expect ~1-1.5h.
"""
from __future__ import annotations

import pytest

from evaluation.scripts import run_day22_live_verification


@pytest.mark.slow
def test_run_day23_live_verification(client):
    result = run_day22_live_verification.main(client)
    assert result["final_status"] in ("COMPLETED", "WAITING_FOR_HUMAN_INPUT")

    project_id = result["project_id"]
    contradictions = client.get(f"/projects/{project_id}/contradictions").json()
    ambiguities = client.get(f"/projects/{project_id}/ambiguities").json()
    assert isinstance(contradictions, list)
    assert isinstance(ambiguities, list)

    plan = client.get(f"/projects/{project_id}/plan").json()
    dependencies = plan["raid"]["dependencies"]
    if dependencies:
        assert all(d["description"] and d["suggested_resolution"] for d in dependencies)

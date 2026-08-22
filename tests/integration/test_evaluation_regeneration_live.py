"""Live verification for selective artifact regeneration. Marked slow — needs one full base
pipeline run (~1-2h) plus two regeneration calls on top.
"""
from __future__ import annotations

import pytest

from evaluation.scripts import run_regeneration_verification


@pytest.mark.slow
def test_regeneration_live(client):
    result = run_regeneration_verification.main(client)
    assert result["sprint_plan_regenerated"] is True, result["sprint_plan_response_detail"]
    assert result["tasks_raid_regenerated"] is True, result["tasks_raid_response_detail"]
    assert result["version_count"] >= 3  # base + 2 regenerations
    assert result["approval_status_after"] != "APPROVED"

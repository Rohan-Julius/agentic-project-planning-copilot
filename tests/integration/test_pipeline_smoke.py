"""Full-pipeline smoke test (Day 15, spec §23): upload -> index -> live agentic workflow
-> both human gates -> export, using scenario 1 (leave management) end-to-end. Live Ollama +
in-memory Qdrant, same pattern as tests/unit/test_workflow_graph.py's live-agent tests.

Marked `slow`: a single live Requirement Analyst call alone can take on the order of minutes
on CPU-only local inference, and Planning makes several sequential calls after it — this test
is excluded from the default `pytest` run (see pyproject.toml's `addopts`) and must be run
explicitly with `pytest -m slow`.
"""
from __future__ import annotations

from pathlib import Path

import pytest

SCENARIO_1_PATH = (
    Path(__file__).resolve().parents[2]
    / "evaluation"
    / "datasets"
    / "scenario_1_leave_management"
    / "requirements.md"
)


def _latest_recommend_action(client, project_id: str) -> str | None:
    events = client.get(f"/projects/{project_id}/workflow/events").json()
    for event in reversed(events):
        if event["agent"] == "Supervisor" and event["action"].startswith("RECOMMEND_"):
            return event["action"]
    return None


@pytest.mark.slow
def test_full_pipeline_completes_end_to_end_for_a_real_uploaded_document(client):
    create_resp = client.post(
        "/projects",
        json={
            "name": "Day15 Smoke - Leave Management",
            "description": "full pipeline smoke test",
            "methodology": "agile_scrum",
        },
    )
    assert create_resp.status_code == 201
    project_id = create_resp.json()["project_id"]

    with SCENARIO_1_PATH.open("rb") as f:
        upload_resp = client.post(
            f"/projects/{project_id}/documents",
            files={"file": ("requirements.md", f, "text/markdown")},
            data={"document_type": "business_requirement"},
        )
    assert upload_resp.status_code == 201

    index_resp = client.post(f"/projects/{project_id}/index")
    assert index_resp.status_code == 200
    assert index_resp.json()["chunk_count"] > 0
    assert index_resp.json()["errors"] == {}

    start_resp = client.post(f"/projects/{project_id}/workflow/start")
    assert start_resp.status_code == 200

    status = client.get(f"/projects/{project_id}/workflow/status").json()["status"]
    attempts = 0
    while status == "WAITING_FOR_HUMAN_INPUT" and attempts < 6:
        action = _latest_recommend_action(client, project_id)
        if action == "RECOMMEND_WAIT_FOR_FINAL_APPROVAL":
            approve_resp = client.post(f"/projects/{project_id}/plan/approve")
        else:
            approve_resp = client.post(f"/projects/{project_id}/clarifications/approve")
        assert approve_resp.status_code == 200
        status = client.get(f"/projects/{project_id}/workflow/status").json()["status"]
        attempts += 1

    assert status == "COMPLETED", (
        f"pipeline did not reach COMPLETED (status={status}); "
        f"events: {client.get(f'/projects/{project_id}/workflow/events').json()}"
    )

    for export_path in ("json", "markdown", "jira-csv", "zip"):
        export_resp = client.get(f"/projects/{project_id}/export/{export_path}")
        assert export_resp.status_code == 200, f"export/{export_path} failed"

    export_json = client.get(f"/projects/{project_id}/export/json").json()
    assert export_json["export_metadata"]["approval_status"] == "APPROVED"

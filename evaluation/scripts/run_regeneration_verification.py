"""Live verification (stretch goal round): confirms selective regeneration (sprint plan,
tasks/deps/RAID) actually works against a real plan and correctly resets final_approved
(§20.5). Reuses Day 22/23's scenario-1 live-verification script to get a real, approved plan
first, then regenerates both artifacts against it — much cheaper than a second full pipeline
run since Requirement Analyst/epics/stories are already done by that point.
"""
from __future__ import annotations

from evaluation.scripts import run_day22_live_verification


def main(client) -> dict:
    base_result = run_day22_live_verification.main(client)
    project_id = base_result["project_id"]

    # Found live (first attempt at this run): the base pipeline can controlled-stop with no
    # plan ever saved (e.g. a genuine, pre-existing small-model reliability issue — the
    # stories-generation call returning truncated/invalid JSON twice in a row, exhausting
    # §20.1's one retry). That's not a Tier-1 regeneration bug; blindly proceeding into
    # regenerate/approve calls against a nonexistent plan just produces a confusing 404 far
    # from its real cause. Check directly rather than assume the base run always succeeds.
    plan_check = client.get(f"/projects/{project_id}/plan")
    if plan_check.status_code != 200:
        raise RuntimeError(
            f"Base pipeline run did not produce a plan for project {project_id!r} "
            f"(final_status={base_result.get('final_status')!r}, "
            f"GET .../plan -> {plan_check.status_code}: {plan_check.text}). "
            "This is a base-pipeline failure (see server logs for the real cause, e.g. a "
            "live-model JSON-validation failure), not a regeneration bug — rerun."
        )

    # Approve the plan first (if not already) so we can prove regeneration resets it.
    client.post(f"/projects/{project_id}/plan/approve")
    export_before = client.get(f"/projects/{project_id}/export/json").json()

    sprint_resp = client.post(f"/projects/{project_id}/plan/regenerate/sprint-plan")
    tasks_resp = client.post(f"/projects/{project_id}/plan/regenerate/tasks-deps-raid")
    export_after = client.get(f"/projects/{project_id}/export/json").json()
    versions = client.get(f"/projects/{project_id}/plan/versions").json()

    # approval_status is nested under export_metadata, not top-level (build_json_export in
    # app/services/export_service.py) — confirmed by reading the code, not assumed.
    return {
        "project_id": project_id,
        "sprint_plan_regenerated": sprint_resp.status_code == 200,
        "sprint_plan_response_detail": None if sprint_resp.status_code == 200 else sprint_resp.json(),
        "tasks_raid_regenerated": tasks_resp.status_code == 200,
        "tasks_raid_response_detail": None if tasks_resp.status_code == 200 else tasks_resp.json(),
        "approval_status_before": export_before.get("export_metadata", {}).get("approval_status"),
        "approval_status_after": export_after.get("export_metadata", {}).get("approval_status"),
        "version_count": len(versions),
    }

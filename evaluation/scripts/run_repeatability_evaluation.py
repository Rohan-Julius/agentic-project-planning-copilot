"""Day 20 repeatability evaluation (spec §24.8): runs scenario 2 (E-Commerce Payments) through
3 independent fresh projects, each driven all the way to COMPLETED via the real API (same
gate-loop pattern as tests/integration/test_pipeline_smoke.py), and captures everything §24.8
asks to compare: requirement count, epic count, story count, requirement coverage
(traceability), unsupported claims / schema-validation failures (validate_project_plan), and
reviewer decisions.

Run #1's captured plan doubles as the baseline for Day 20's §24.6 manual quality scoring and
§24.7's seeded-error variants (evaluation/scripts/run_seeded_error_evaluation.py) — no
separate baseline run needed.
"""
from __future__ import annotations

import json
from pathlib import Path

from evaluation.scripts.run_extraction_evaluation import compute_agent_durations

REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"
DATASETS_DIR = Path(__file__).resolve().parents[1] / "datasets"
SCENARIO_PATH = DATASETS_DIR / "scenario_2_ecommerce_payments" / "requirements.md"


def _latest_recommend_action(client, project_id: str) -> str | None:
    events = client.get(f"/projects/{project_id}/workflow/events").json()
    for event in reversed(events):
        if event["agent"] == "Supervisor" and event["action"].startswith("RECOMMEND_"):
            return event["action"]
    return None


def run_once(client, run_number: int) -> dict:
    create_resp = client.post(
        "/projects",
        json={"name": f"Day20 Repeatability Run {run_number}", "methodology": "agile_scrum"},
    )
    assert create_resp.status_code == 201, create_resp.text
    project_id = create_resp.json()["project_id"]

    with SCENARIO_PATH.open("rb") as f:
        upload_resp = client.post(
            f"/projects/{project_id}/documents",
            files={"file": ("requirements.md", f, "text/markdown")},
            data={"document_type": "business_requirement"},
        )
    assert upload_resp.status_code == 201, upload_resp.text

    index_resp = client.post(f"/projects/{project_id}/index")
    assert index_resp.status_code == 200, index_resp.text

    start_resp = client.post(f"/projects/{project_id}/workflow/start")
    assert start_resp.status_code == 200, start_resp.text

    status = client.get(f"/projects/{project_id}/workflow/status").json()["status"]
    revision_occurred = False
    attempts = 0
    while status == "WAITING_FOR_HUMAN_INPUT" and attempts < 6:
        action = _latest_recommend_action(client, project_id)
        if action == "RECOMMEND_WAIT_FOR_FINAL_APPROVAL":
            approve_resp = client.post(f"/projects/{project_id}/plan/approve")
        else:
            approve_resp = client.post(f"/projects/{project_id}/clarifications/approve")
        assert approve_resp.status_code == 200, approve_resp.text
        run = approve_resp.json()
        if run.get("revision_count", 0) > 0:
            revision_occurred = True
        status = client.get(f"/projects/{project_id}/workflow/status").json()["status"]
        attempts += 1

    plan_resp = client.get(f"/projects/{project_id}/plan")
    plan = plan_resp.json() if plan_resp.status_code == 200 else None
    review_resp = client.get(f"/projects/{project_id}/review")
    review = review_resp.json() if review_resp.status_code == 200 else None

    # Per-agent-call durations (§21 "Generation duration") — reuses Day 19's timestamp-pairing
    # approach rather than duplicating it, since WorkflowEvent.duration_ms is still never
    # populated at the source (flagged, not fixed, in Day 19's report).
    events = client.get(f"/projects/{project_id}/workflow/events").json()
    agent_durations = compute_agent_durations(events)
    total_duration_seconds = round(sum(d["duration_seconds"] for d in agent_durations), 1)

    validation_is_valid = None
    validation_error_count = None
    traceability_coverage_pct = None
    if plan is not None:
        from app.tools.validation_tools import check_traceability, validate_project_plan

        session_factory = client.session_factory
        validation = validate_project_plan(project_id, session_factory=session_factory)
        validation_is_valid = validation.is_valid
        validation_error_count = len(validation.errors)
        # check_traceability() returns TraceabilityResult(matrix=TraceabilityMatrix(rows=...),
        # coverage_gaps=[...]) — matrix.rows are TraceabilityRow Pydantic objects (attribute
        # access, not dict .get()), and coverage_gaps is already the list of requirement_ids
        # with no epic_id, so "coverage %" is directly (total - gaps) / total.
        traceability = check_traceability(project_id, session_factory=session_factory)
        total = len(traceability.matrix.rows) or 1
        traceability_coverage_pct = round(
            (total - len(traceability.coverage_gaps)) / total * 100, 1
        )

    return {
        "run_number": run_number,
        "project_id": project_id,
        "final_status": status,
        "requirement_count": len(client.get(f"/projects/{project_id}/requirements").json()),
        "epic_count": len(plan["epics"]) if plan else None,
        "story_count": len(plan["stories"]) if plan else None,
        "reviewer_decision": review["decision"] if review else None,
        "revision_occurred": revision_occurred,
        "validation_is_valid": validation_is_valid,
        "validation_error_count": validation_error_count,
        "traceability_coverage_pct": traceability_coverage_pct,
        "agent_durations": agent_durations,
        "total_duration_seconds": total_duration_seconds,
        "plan": plan,
    }


def write_report(results: list[dict]) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    for r in results:
        (REPORTS_DIR / f"day20_repeatability_run{r['run_number']}_plan.json").write_text(
            json.dumps(r["plan"], indent=2, default=str) if r["plan"] else "null"
        )

    lines = [
        "# Day 20 Repeatability Evaluation (spec §24.8) — scenario 2, 3 independent runs",
        "",
        "| Run | Status | Reqs | Epics | Stories | Reviewer decision | Revision? | Valid? | Errors | Traceability | Total agent time |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['run_number']} | {r['final_status']} | {r['requirement_count']} | "
            f"{r['epic_count']} | {r['story_count']} | {r['reviewer_decision']} | "
            f"{r['revision_occurred']} | {r['validation_is_valid']} | "
            f"{r['validation_error_count']} | {r['traceability_coverage_pct']}% | "
            f"{r['total_duration_seconds']}s ({r['total_duration_seconds'] / 60:.1f} min) |"
        )
    lines.append("")
    lines.append("## Per-agent-call durations")
    for r in results:
        lines.append(f"\n### Run {r['run_number']}")
        for d in r["agent_durations"]:
            lines.append(
                f"- {d['agent']} ({d['stage']}, {d['action']}, {d['outcome']}): "
                f"{d['duration_seconds']}s"
            )
    (REPORTS_DIR / "day20_repeatability_evaluation.md").write_text("\n".join(lines))


def main(client) -> list[dict]:
    results = [run_once(client, n) for n in (1, 2, 3)]
    write_report(results)
    return results


if __name__ == "__main__":
    import httpx

    main(httpx.Client(base_url="http://localhost:8000", timeout=3600))

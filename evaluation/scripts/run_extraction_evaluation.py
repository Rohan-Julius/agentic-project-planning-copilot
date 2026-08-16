"""Day 19 evaluation script (spec §24.1, §24.2, §24.4): runs each of the 3 synthetic
scenarios through the real API (upload -> index -> live Requirement Analyst via
POST /workflow/start), captures the raw requirements/clarifications/tool-call events, and
writes one JSON artifact + one automated-metrics markdown report to evaluation/reports/.

Recall against the gold-standard requirement lists (evaluation/expected_results/) and
clarification-quality scoring are NOT computed here — both require human judgment per spec
§24.1/§24.2 ("manually assess") and are written directly into
evaluation/reports/day19_evaluation_report.md after reading this script's JSON output.

Per-agent-call duration (how long each live Supervisor/Requirement Analyst generation
actually took, §21 "Generation duration") is computed from the WorkflowEvent log's own
timestamps — pairing each agent+stage's IN_PROGRESS event with its next SUCCESS/ERROR event
for the same agent+stage, since action names can differ between the two (e.g. Supervisor logs
"EVALUATE_STATE" IN_PROGRESS but "RECOMMEND_<action>" on success).

Callable standalone (`python evaluation/scripts/run_extraction_evaluation.py`) against a real
running dev server, or imported and driven with an in-process TestClient (see
tests/integration/test_evaluation_day19.py) for a self-contained run needing only live Ollama.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"
DATASETS_DIR = Path(__file__).resolve().parents[1] / "datasets"

SCENARIOS = [
    ("scenario_1_leave_management", "Leave Management"),
    ("scenario_2_ecommerce_payments", "E-Commerce Payment Integration"),
    ("scenario_3_ambiguous_support", "Ambiguous Customer Support Assistant"),
]

# Spec §9's named tools, plus this codebase's legitimate internal support reads/writes
# already audited during Day 17/18 (get_requirements, get_current_plan_version_id,
# save_reviewer_report, load_current_plan) — anything outside this set is a real §20.2 finding.
PERMITTED_TOOLS = {
    "search_project_documents", "search_company_standards", "get_project_information",
    "save_requirements", "save_clarification_questions", "get_clarification_answers",
    "save_planning_artifacts", "validate_project_plan", "check_traceability",
    "find_supporting_evidence", "export_jira_csv",
    "get_requirements", "get_current_plan_version_id", "save_reviewer_report",
    "load_current_plan",
}


def run_scenario(client, scenario_dir: str, project_name: str) -> dict:
    doc_path = DATASETS_DIR / scenario_dir / "requirements.md"

    create_resp = client.post(
        "/projects",
        json={"name": f"Day19 Eval - {project_name}", "methodology": "agile_scrum"},
    )
    assert create_resp.status_code == 201, create_resp.text
    project_id = create_resp.json()["project_id"]

    with doc_path.open("rb") as f:
        upload_resp = client.post(
            f"/projects/{project_id}/documents",
            files={"file": ("requirements.md", f, "text/markdown")},
            data={"document_type": "business_requirement"},
        )
    assert upload_resp.status_code == 201, upload_resp.text

    index_resp = client.post(f"/projects/{project_id}/index")
    assert index_resp.status_code == 200, index_resp.text
    assert index_resp.json()["errors"] == {}, index_resp.json()["errors"]

    start_resp = client.post(f"/projects/{project_id}/workflow/start")
    assert start_resp.status_code == 200, start_resp.text

    return {
        "scenario": scenario_dir,
        "project_id": project_id,
        "workflow_status": start_resp.json()["status"],
        "requirements": client.get(f"/projects/{project_id}/requirements").json(),
        "clarifications": client.get(f"/projects/{project_id}/clarifications").json(),
        "events": client.get(f"/projects/{project_id}/workflow/events").json(),
    }


def _count_by(items: list[dict], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item[field]] = counts.get(item[field], 0) + 1
    return counts


def compute_agent_durations(events: list[dict]) -> list[dict]:
    """Pairs each (agent, stage)'s IN_PROGRESS event with its next SUCCESS/ERROR *stage
    completion* event for that same agent+stage, in timestamp order, and returns the elapsed
    seconds for each — the actual live generation duration per agent call (§21 "Generation
    duration"), not logged anywhere else since WorkflowEvent.duration_ms is never populated
    in this codebase.

    CALL_TOOL events are intermediate informational sub-logs *within* a still-in-progress
    stage (e.g. RequirementAnalyst logs one per tool it calls before the LLM generation even
    starts) — they must be skipped when looking for the closing event, or the very first tool
    call (milliseconds after IN_PROGRESS) gets mistaken for the whole stage completing.
    """
    open_calls: dict[tuple[str, str], tuple[str, datetime]] = {}
    durations = []
    for event in sorted(events, key=lambda e: e["timestamp"]):
        key = (event["agent"], event["stage"])
        ts = datetime.fromisoformat(event["timestamp"])
        if event["status"] == "IN_PROGRESS":
            open_calls[key] = (event["action"], ts)
        elif event["action"] == "CALL_TOOL":
            continue
        elif event["status"] in ("SUCCESS", "ERROR") and key in open_calls:
            start_action, start_ts = open_calls.pop(key)
            durations.append({
                "agent": event["agent"],
                "stage": event["stage"],
                "action": start_action,
                "outcome": event["status"],
                "duration_seconds": round((ts - start_ts).total_seconds(), 1),
            })
    return durations


def compute_automated_metrics(result: dict) -> dict:
    requirements = result["requirements"]
    clarifications = result["clarifications"]
    source_backed = [r for r in requirements if r["classification"] == "SOURCE_BACKED"]
    source_backed_with_citation = [r for r in source_backed if r["source_references"]]
    tool_calls = [e["tool"] for e in result["events"] if e.get("tool")]

    return {
        "requirement_count": len(requirements),
        "requirements_by_category": _count_by(requirements, "category"),
        "requirements_by_classification": _count_by(requirements, "classification"),
        "source_backed_citation_rate": (
            len(source_backed_with_citation) / len(source_backed) if source_backed else None
        ),
        "clarification_question_count": len(clarifications),
        "clarification_questions_by_category": _count_by(clarifications, "category"),
        "clarification_questions_by_priority": _count_by(clarifications, "priority"),
        "tool_calls_in_order": tool_calls,
        "unpermitted_tool_calls": sorted({t for t in tool_calls if t not in PERMITTED_TOOLS}),
        "agent_durations": compute_agent_durations(result["events"]),
    }


def write_reports(all_results: list[dict]) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    for result in all_results:
        (REPORTS_DIR / f"{result['scenario']}_raw_result.json").write_text(
            json.dumps(result, indent=2, default=str)
        )

    lines = ["# Day 19 Automated Metrics (spec §24.1, §24.2, §24.4)", ""]
    for result in all_results:
        m = compute_automated_metrics(result)
        citation_rate = m["source_backed_citation_rate"]
        lines += [
            f"## {result['scenario']}",
            f"- Workflow status: {result['workflow_status']}",
            f"- Requirements extracted: {m['requirement_count']}",
            f"- By category: {m['requirements_by_category']}",
            f"- By classification: {m['requirements_by_classification']}",
            "- SOURCE_BACKED citation rate: "
            + ("N/A (none)" if citation_rate is None else f"{citation_rate:.0%}"),
            f"- Clarification questions: {m['clarification_question_count']}",
            f"  - By category: {m['clarification_questions_by_category']}",
            f"  - By priority: {m['clarification_questions_by_priority']}",
            f"- Tool calls (in order): {m['tool_calls_in_order']}",
            f"- Unpermitted tool calls (§20.2 finding if non-empty): {m['unpermitted_tool_calls']}",
            "- Agent call durations:",
        ]
        for d in m["agent_durations"]:
            lines.append(
                f"  - {d['agent']} ({d['stage']}, {d['action']}, {d['outcome']}): "
                f"{d['duration_seconds']}s"
            )
        lines.append("")
    (REPORTS_DIR / "day19_automated_metrics.md").write_text("\n".join(lines))


def main(client) -> list[dict]:
    all_results = [run_scenario(client, scenario_dir, name) for scenario_dir, name in SCENARIOS]
    write_reports(all_results)
    return all_results


if __name__ == "__main__":
    import httpx

    main(httpx.Client(base_url="http://localhost:8000"))

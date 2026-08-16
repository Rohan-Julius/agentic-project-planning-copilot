"""Day 19 agent-routing evaluation (spec §24.3) — runs the REAL Supervisor Agent (live
Ollama, no mocked run_agent) against >=15 distinct ProjectWorkflowState situations and checks
whether its actual decision matches the expected next action.

This is deliberately NOT the same kind of test as tests/unit/test_supervisor_agent.py's
existing table, which mocks run_agent to return exactly the value under assertion
(tautological — flagged, not fixed, since Day 9's PROJECT_PLAN.md notes). This script is the
genuine §24.3 evaluation: "Check whether the Supervisor selects the correct next action"
against its real reasoning over a real prompt, not a canned response.

Also captures each call's wall-clock duration directly (time.perf_counter) — the Supervisor's
own generation latency, per situation, since WorkflowEvent.duration_ms is never populated in
this codebase (see run_extraction_evaluation.py's compute_agent_durations for the API-level
equivalent).
"""
from __future__ import annotations

import time
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from app.agents.supervisor import run_supervisor_agent
from app.models.project import ProjectRecord

REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"


def _state(project_id="proj_eval", **overrides) -> dict:
    state = {
        "project_id": project_id,
        "current_stage": "start",
        "next_action": None,
        "document_ids": [],
        "requirement_ids": [],
        "unresolved_question_ids": [],
        "requirement_analysis_attempts": 0,
        "clarification_approved": False,
        "plan_version_id": None,
        "reviewer_decision": None,
        "reviewer_issue_ids": [],
        "revision_count": 0,
        "final_approved": False,
        "errors": [],
        "workflow_events": [],
    }
    state.update(overrides)
    return state


SITUATIONS = [
    ("no_documents_analyzed", _state(), "RUN_REQUIREMENT_ANALYST"),
    (
        "requirements_extracted_questions_pending",
        _state(requirement_ids=["REQ-1"], unresolved_question_ids=["Q-1"]),
        "WAIT_FOR_CLARIFICATIONS",
    ),
    (
        "requirements_extracted_no_questions_unapproved",
        _state(requirement_ids=["REQ-1"], unresolved_question_ids=[]),
        "WAIT_FOR_CLARIFICATIONS",
    ),
    (
        "clarifications_approved_ready_for_planning",
        _state(requirement_ids=["REQ-1"], clarification_approved=True),
        "RUN_PLANNING_AGENT",
    ),
    (
        "plan_generated_awaiting_review",
        _state(requirement_ids=["REQ-1"], clarification_approved=True, plan_version_id="v1"),
        "RUN_REVIEWER_AGENT",
    ),
    (
        "reviewer_requests_revision_available",
        _state(
            requirement_ids=["REQ-1"], clarification_approved=True, plan_version_id="v1",
            reviewer_decision="REVISION_REQUIRED", revision_count=0,
        ),
        "REVISE_PLAN",
    ),
    (
        "reviewer_requests_revision_limit_reached",
        _state(
            requirement_ids=["REQ-1"], clarification_approved=True, plan_version_id="v1",
            reviewer_decision="REVISION_REQUIRED", revision_count=1,
        ),
        "WAIT_FOR_FINAL_APPROVAL",
    ),
    (
        "reviewer_pass",
        _state(
            requirement_ids=["REQ-1"], clarification_approved=True, plan_version_id="v1",
            reviewer_decision="PASS",
        ),
        "WAIT_FOR_FINAL_APPROVAL",
    ),
    (
        "reviewer_pass_with_warnings",
        _state(
            requirement_ids=["REQ-1"], clarification_approved=True, plan_version_id="v1",
            reviewer_decision="PASS_WITH_WARNINGS",
        ),
        "WAIT_FOR_FINAL_APPROVAL",
    ),
    (
        "post_revision_reviewer_now_passes",
        _state(
            requirement_ids=["REQ-1"], clarification_approved=True, plan_version_id="v2",
            reviewer_decision="PASS", revision_count=1,
        ),
        "WAIT_FOR_FINAL_APPROVAL",
    ),
    (
        "final_approved_ready_for_export",
        _state(
            requirement_ids=["REQ-1"], clarification_approved=True, plan_version_id="v1",
            reviewer_decision="PASS", final_approved=True,
        ),
        "EXPORT_PLAN",
    ),
    (
        "final_approved_with_prior_revision",
        _state(
            requirement_ids=["REQ-1"], clarification_approved=True, plan_version_id="v2",
            reviewer_decision="PASS_WITH_WARNINGS", revision_count=1, final_approved=True,
        ),
        "EXPORT_PLAN",
    ),
    (
        "single_error_recorded",
        _state(errors=["Ollama not reachable at http://localhost:11434"]),
        "STOP_WITH_ERROR",
    ),
    (
        "multiple_errors_recorded",
        _state(errors=[f"error {i}" for i in range(5)]),
        "STOP_WITH_ERROR",
    ),
    (
        "error_recorded_despite_otherwise_complete_state",
        _state(
            requirement_ids=["REQ-1"], clarification_approved=True, plan_version_id="v1",
            reviewer_decision="PASS", final_approved=True,
            errors=["Schema validation failed 2 times"],
        ),
        "STOP_WITH_ERROR",
    ),
    (
        "large_scale_requirements_no_questions_unapproved",
        _state(requirement_ids=[f"REQ-{i}" for i in range(80)], unresolved_question_ids=[]),
        "WAIT_FOR_CLARIFICATIONS",
    ),
    (
        "many_clarification_questions_pending",
        _state(
            requirement_ids=["REQ-1"],
            unresolved_question_ids=[f"Q-{i}" for i in range(15)],
        ),
        "WAIT_FOR_CLARIFICATIONS",
    ),
]


def main(session_factory: sessionmaker) -> list[dict]:
    session = session_factory()
    session.add(ProjectRecord(project_id="proj_eval", name="Routing Evaluation Project"))
    session.commit()

    results = []
    for name, state, expected in SITUATIONS:
        start = time.perf_counter()
        decision = run_supervisor_agent(state, session)
        elapsed = round(time.perf_counter() - start, 1)
        results.append({
            "situation": name,
            "expected": expected,
            "actual": decision.next_action,
            "passed": decision.next_action == expected,
            "reason": decision.reason,
            "duration_seconds": elapsed,
        })
    session.close()

    write_report(results)
    return results


def write_report(results: list[dict]) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    passed = sum(1 for r in results if r["passed"])
    durations = [r["duration_seconds"] for r in results]
    lines = [
        "# Day 19 Agent Routing Evaluation (spec §24.3)",
        "",
        f"**Pass rate: {passed}/{len(results)} ({passed / len(results):.0%})**",
        f"**Supervisor call duration — mean: {sum(durations) / len(durations):.1f}s, "
        f"min: {min(durations):.1f}s, max: {max(durations):.1f}s**",
        "",
        "| Situation | Expected | Actual | Pass | Duration (s) | Supervisor's Reason |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        mark = "PASS" if r["passed"] else "FAIL"
        lines.append(
            f"| {r['situation']} | {r['expected']} | {r['actual']} | {mark} | "
            f"{r['duration_seconds']} | {r['reason']} |"
        )
    (REPORTS_DIR / "day19_routing_evaluation.md").write_text("\n".join(lines))


if __name__ == "__main__":
    from app.database.session import get_sessionmaker

    main(get_sessionmaker())

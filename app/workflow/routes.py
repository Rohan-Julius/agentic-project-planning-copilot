"""Deterministic routing table (Day 7, DESIGN.md §7.3, spec §10/§19) — the enforcement
point. It never trusts an agent's own judgment to respect a loop limit: `route_next_node`
computes the next node from `ProjectWorkflowState` alone, and the Supervisor Agent's own
`SupervisorDecision` (Day 8) is advisory context for the UI/audit trail, not the routing
authority.

Two deliberate departures from DESIGN.md's literal table are documented in
docs/DAY7_UNDERSTANDING.md (decisions 2 and 3): the clarification-approval condition is
broadened to not require `unresolved_question_ids`, and `final_approved` is checked before
the reviewer-decision rules.
"""
from __future__ import annotations

from app.workflow.state import ProjectWorkflowState

NODE_REQUIREMENT_ANALYST = "requirement_analyst"
NODE_CLARIFICATION_GATE = "clarification_gate"
NODE_PLANNING = "planning"
NODE_REVIEWER = "reviewer"
NODE_PLAN_REVISION = "plan_revision"
NODE_FINAL_GATE = "final_gate"
NODE_EXPORT = "export"
NODE_STOP_ERROR = "stop_error"

ALL_NODES = (
    NODE_REQUIREMENT_ANALYST,
    NODE_CLARIFICATION_GATE,
    NODE_PLANNING,
    NODE_REVIEWER,
    NODE_PLAN_REVISION,
    NODE_FINAL_GATE,
    NODE_EXPORT,
    NODE_STOP_ERROR,
)


def route_next_node(state: ProjectWorkflowState) -> str:
    """DESIGN.md §7.3 routing table, in priority order (first match wins)."""
    # Any recorded error is an unconditional controlled stop (§20.1) — elevated ahead of
    # the spec table's own ordering so a stub/failed node can never loop forever waiting
    # for a condition it will never satisfy (see DAY7_UNDERSTANDING.md decision 1).
    if state["errors"]:
        return NODE_STOP_ERROR

    if not state["requirement_ids"]:
        # §20.1: requirement-analysis retry is capped at one — a legitimately
        # document-less/evidence-less project can honestly come back with zero
        # requirements (the agent must not invent them), and without this cap that
        # would loop back into requirement_analyst forever instead of controlled-stopping.
        if state["requirement_analysis_attempts"] >= 2:
            return NODE_STOP_ERROR
        return NODE_REQUIREMENT_ANALYST

    # Broadened from the spec table's "unresolved_question_ids non-empty ∧ ¬approved":
    # §11 requires an explicit human approval before planning starts even when the
    # Requirement Analyst found zero clarification-worthy questions (decision 2).
    if not state["clarification_approved"]:
        return NODE_CLARIFICATION_GATE

    # Checked before the reviewer-decision rules below (decision 3): once a human has
    # approved the final plan, export always wins regardless of whatever stale
    # reviewer_decision is still sitting in state.
    if state["final_approved"]:
        return NODE_EXPORT

    if state["plan_version_id"] is None:
        return NODE_PLANNING

    if state["reviewer_decision"] is None:
        return NODE_REVIEWER

    if state["reviewer_decision"] == "REVISION_REQUIRED":
        return NODE_PLAN_REVISION if state["revision_count"] < 1 else NODE_FINAL_GATE

    if state["reviewer_decision"] in ("PASS", "PASS_WITH_WARNINGS"):
        return NODE_FINAL_GATE

    return NODE_STOP_ERROR

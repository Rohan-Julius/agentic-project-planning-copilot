"""Supervisor Agent (DESIGN.md §8.1, spec §7.1) — routing only, no artifacts."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.runner import run_agent
from app.schemas.agents import SupervisorDecision
from app.workflow.state import ProjectWorkflowState


def _summarize_state(state: ProjectWorkflowState) -> str:
    """Generate a natural-language summary of workflow state for the Supervisor to reason about."""
    parts = []

    parts.append(f"Project: {state['project_id']}")
    parts.append(f"Current stage: {state['current_stage']}")

    if state["errors"]:
        parts.append(f"⚠️  Errors recorded: {len(state['errors'])} — workflow is blocked")
        for err in state["errors"][:3]:  # Show first 3 errors
            parts.append(f"  - {err}")
        if len(state["errors"]) > 3:
            parts.append(f"  ... and {len(state['errors']) - 3} more")
        parts.append("")

    if not state["requirement_ids"]:
        parts.append("✗ Requirement analysis: NOT STARTED")
    else:
        parts.append(f"✓ Requirement analysis: COMPLETE ({len(state['requirement_ids'])} requirements)")

    if state["unresolved_question_ids"]:
        parts.append(
            f"? Clarifications: PENDING ({len(state['unresolved_question_ids'])} questions awaiting review)"
        )
    elif state["requirement_ids"]:
        parts.append("✓ Clarifications: NONE (or all resolved)")

    if not state["clarification_approved"] and state["requirement_ids"]:
        parts.append("⏸  Clarification approval: AWAITING human approval to proceed")

    if not state["plan_version_id"] and state["clarification_approved"]:
        parts.append("✗ Planning: NOT STARTED")
    elif state["plan_version_id"]:
        parts.append(f"✓ Planning: COMPLETE (version {state['plan_version_id'][:8]}...)")

    if state["reviewer_decision"] is None and state["plan_version_id"]:
        parts.append("✗ Review: NOT STARTED")
    elif state["reviewer_decision"]:
        parts.append(f"✓ Review: COMPLETE (decision: {state['reviewer_decision']})")

    if state["reviewer_decision"] == "REVISION_REQUIRED" and state["revision_count"] < 1:
        parts.append(f"↻ Revision: AVAILABLE (revision_count={state['revision_count']})")
    elif state["reviewer_decision"] == "REVISION_REQUIRED" and state["revision_count"] >= 1:
        parts.append(
            f"↻ Revision: EXHAUSTED (max 1 allowed, count={state['revision_count']}) — "
            "the plan still has open issues, but no more revisions are allowed, so the "
            "correct next action is WAIT_FOR_FINAL_APPROVAL, not WAIT_FOR_CLARIFICATIONS "
            "(clarifications were already approved earlier in this run) and not REVISE_PLAN."
        )
    elif state["revision_count"] >= 1:
        parts.append(f"↻ Revision: EXHAUSTED (max 1 allowed, count={state['revision_count']})")

    if state["final_approved"]:
        parts.append("✓ Final approval: APPROVED — ready to export")

    return "\n".join(parts)


def run_supervisor_agent(state: ProjectWorkflowState, session: Session) -> SupervisorDecision:
    """Emit a routing decision based on the workflow state.

    Input: workflow state (IDs/flags/counters only — no document content)
    Output: SupervisorDecision with one of 8 actions
    Tools: none

    The decision is advisory; the deterministic router (app/workflow/routes.py) validates
    it against counters and is the actual enforcement point (§20.1).

    Args:
        state: current ProjectWorkflowState
        session: SQLAlchemy session (unused by Supervisor, but passed for consistency)

    Returns:
        SupervisorDecision with next_action ∈ 8 allowed actions
    """
    state_summary = _summarize_state(state)

    prompt = f"""You are a workflow supervisor for an agentic project planning system.

Your job is to analyze the workflow state and recommend exactly one next action. You NEVER:
- Generate or modify documents, stories, or artifacts
- Approve clarifications or final plans (that's the human's job)
- Create unbounded loops

The 8 allowed actions are:
1. RUN_REQUIREMENT_ANALYST — extract requirements from documents
2. WAIT_FOR_CLARIFICATIONS — pause until human reviews clarification questions
3. RUN_PLANNING_AGENT — synthesize epics, stories, tasks from approved requirements
4. RUN_REVIEWER_AGENT — QA the plan independently
5. REVISE_PLAN — revise once if reviewer found issues (max 1 revision total)
6. WAIT_FOR_FINAL_APPROVAL — pause until human approves the final plan
7. EXPORT_PLAN — generate JSON, CSV, Markdown, ZIP exports
8. STOP_WITH_ERROR — controlled stop due to unrecoverable error

Current workflow state:
{state_summary}

Return JSON with:
  - next_action: exactly one of the 8 above
  - reason: one sentence explaining why
  - required_inputs: list of what the next node needs (e.g., ["documents"], ["clarification_review"])

Return only valid JSON, no other text."""

    return run_agent(
        agent_name="supervisor",
        prompt=prompt,
        output_model=SupervisorDecision,
        tools=[],
    )

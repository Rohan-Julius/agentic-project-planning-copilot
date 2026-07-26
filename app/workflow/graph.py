"""LangGraph state graph (Day 7, DESIGN.md §7.1/§7.2, spec §10/§19).

As of Day 13, only `export` remains a stub (ships Day 14, spec §9.11/§16.8). `supervisor`,
`requirement_analyst`, `planning`, `reviewer`, and `plan_revision` are all real nodes; a stub
still records a `WorkflowEvent` and appends to `state["errors"]`, and the router
(`route_next_node`) sends the run straight to `stop_error` on the very next pass, since any
non-empty `errors` is an unconditional controlled stop (see docs/DAY7_UNDERSTANDING.md
decision 1).

`clarification_gate` and `final_gate` are real, not stubs: they only depend on state flags
set by tools/endpoints, never on agent reasoning, so the interrupt/resume machinery itself
is fully functional from Day 7 onward.
"""
from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from app.workflow.events import log_event
from app.workflow.routes import (
    NODE_CLARIFICATION_GATE,
    NODE_EXPORT,
    NODE_FINAL_GATE,
    NODE_PLAN_REVISION,
    NODE_PLANNING,
    NODE_REQUIREMENT_ANALYST,
    NODE_REVIEWER,
    NODE_STOP_ERROR,
    route_next_node,
)
from app.workflow.state import ProjectWorkflowState

# (display agent name, day it ships) — PROJECT_PLAN.md. Only export remains a stub after
# Day 13; planning/reviewer/plan_revision are real nodes below.
_NOT_IMPLEMENTED = {
    NODE_EXPORT: ("Export", 14),
}


def _log(state: ProjectWorkflowState, config: RunnableConfig, **fields: Any) -> None:
    """Uses the `session_factory` threaded through `config["configurable"]` by
    `engine.start_workflow`/`resume_workflow` — never the cached production
    `get_sessionmaker()` singleton directly, so a test-overridden engine (or any future
    caller's engine) is always the one actually written to (see DAY7_UNDERSTANDING.md).
    """
    session = config["configurable"]["session_factory"]()
    try:
        log_event(
            session,
            workflow_run_id=config["configurable"]["thread_id"],
            project_id=state["project_id"],
            **fields,
        )
    finally:
        session.close()


def supervisor_node(state: ProjectWorkflowState, config: RunnableConfig) -> dict:
    """Real Supervisor Agent node (Day 8).

    Emits a routing decision based on the workflow state. The decision is logged and
    set in state (for audit trail), but the deterministic router (route_next_node) is
    the actual authority for loop limits and final routing — never trusts the agent
    to enforce counters (§20.1).
    """
    from app.agents.supervisor import run_supervisor_agent
    from app.agents.runner import AgentError

    session = config["configurable"]["session_factory"]()
    try:
        _log(
            state, config, agent="Supervisor", stage="supervisor",
            action="EVALUATE_STATE", status="IN_PROGRESS",
        )

        decision = run_supervisor_agent(state, session)

        _log(
            state, config, agent="Supervisor", stage="supervisor",
            action=f"RECOMMEND_{decision.next_action}", status="SUCCESS",
        )

        return {
            "current_stage": "supervisor",
            "next_action": decision.next_action,
        }

    except AgentError as e:
        error_msg = str(e)
        _log(
            state, config, agent="Supervisor", stage="supervisor",
            action="ERROR", status="ERROR", error=error_msg,
        )
        return {"errors": [*state["errors"], error_msg]}

    finally:
        session.close()


def requirement_analyst_node(state: ProjectWorkflowState, config: RunnableConfig) -> dict:
    """Requirement Analyst Agent node (Day 9, spec §7.2).

    Extracts structured requirements, identifies contradictions/ambiguities,
    and generates clarification questions. Saves findings to database.
    """
    from app.agents.requirement_analyst import run_requirement_analyst_agent
    from app.agents.runner import AgentError

    attempts = state["requirement_analysis_attempts"] + 1

    try:
        _log(
            state, config, agent="RequirementAnalyst", stage=NODE_REQUIREMENT_ANALYST,
            action="EXTRACT_REQUIREMENTS", status="IN_PROGRESS",
        )

        # Run the agent — threads the same session_factory as `_log` uses (never the
        # cached production get_sessionmaker() singleton), so a test-overridden engine
        # is the one actually read/written (mirrors supervisor_node's pattern). Same for
        # vector_service so retrieval-tool calls hit a test-overridden Qdrant instead of
        # the process-wide get_vector_service() singleton.
        result = run_requirement_analyst_agent(
            project_id=state["project_id"],
            workflow_run_id=config["configurable"]["thread_id"],
            session_factory=config["configurable"]["session_factory"],
            vector_service=config["configurable"].get("vector_service"),
        )

        # Extract IDs from result
        requirement_ids = [req.requirement_id for req in result.requirements]
        unresolved_question_ids = [q.question_id for q in result.clarification_questions]

        _log(
            state, config, agent="RequirementAnalyst", stage=NODE_REQUIREMENT_ANALYST,
            action="EXTRACT_REQUIREMENTS", status="SUCCESS",
            result_count=len(requirement_ids),
            extra={
                "question_count": len(unresolved_question_ids),
                "contradiction_count": len(result.contradictions),
                "ambiguity_count": len(result.ambiguities),
            },
        )

        update: dict = {
            "current_stage": NODE_REQUIREMENT_ANALYST,
            "requirement_ids": requirement_ids,
            "unresolved_question_ids": unresolved_question_ids,
            "requirement_analysis_attempts": attempts,
        }

        # §20.1: maximum one retry. If the agent honestly found nothing extractable
        # twice in a row (no invented requirements per §12.6), controlled-stop instead
        # of letting the router send it back a third time.
        if not requirement_ids and attempts >= 2:
            error_msg = (
                "Requirement Analyst produced no extractable requirements after "
                f"{attempts} attempts (§20.1 retry limit reached) — likely no "
                "documents or evidence available for this project."
            )
            _log(
                state, config, agent="RequirementAnalyst", stage=NODE_REQUIREMENT_ANALYST,
                action="ERROR", status="ERROR", error=error_msg,
            )
            update["errors"] = [*state["errors"], error_msg]

        return update

    except (AgentError, ValueError) as e:
        error_msg = str(e)
        _log(
            state, config, agent="RequirementAnalyst", stage=NODE_REQUIREMENT_ANALYST,
            action="ERROR", status="ERROR", error=error_msg,
        )
        return {
            "errors": [*state["errors"], error_msg],
            "requirement_analysis_attempts": attempts,
        }


def planning_node(state: ProjectWorkflowState, config: RunnableConfig) -> dict:
    """Planning Agent node (Day 13 wiring — agent logic shipped Days 11-12, spec §7.3).

    Runs the full summary->scope->epics->stories->tasks/deps/RAID->sprint sequence and
    persists it as a new plan version; sets state.plan_version_id to that version so the
    router (routes.py §7.3 table) advances to the reviewer next.
    """
    from app.agents.planning import run_planning_agent
    from app.agents.runner import AgentError
    from app.tools.project_tools import get_current_plan_version_id

    try:
        _log(
            state, config, agent="Planning", stage=NODE_PLANNING,
            action="GENERATE_PLAN", status="IN_PROGRESS",
        )

        run_planning_agent(
            project_id=state["project_id"],
            workflow_run_id=config["configurable"]["thread_id"],
            session_factory=config["configurable"]["session_factory"],
            vector_service=config["configurable"].get("vector_service"),
        )
        version_id = get_current_plan_version_id(
            state["project_id"], session_factory=config["configurable"]["session_factory"],
        )

        _log(
            state, config, agent="Planning", stage=NODE_PLANNING,
            action="GENERATE_PLAN", status="SUCCESS",
        )

        return {
            "current_stage": NODE_PLANNING,
            "plan_version_id": version_id,
            # A fresh plan invalidates any prior reviewer verdict from an earlier version.
            "reviewer_decision": None,
        }

    except (AgentError, ValueError) as e:
        error_msg = str(e)
        _log(
            state, config, agent="Planning", stage=NODE_PLANNING,
            action="ERROR", status="ERROR", error=error_msg,
        )
        return {"errors": [*state["errors"], error_msg]}


def reviewer_node(state: ProjectWorkflowState, config: RunnableConfig) -> dict:
    """Reviewer Agent node (Day 13, spec §7.4). Independent QA of the current plan version;
    never rewrites the plan, only judges it (§34 Q6 — the planner never grades its own work).
    """
    from app.agents.reviewer import run_reviewer_agent
    from app.agents.runner import AgentError
    from app.tools.project_tools import save_reviewer_report

    try:
        _log(
            state, config, agent="Reviewer", stage=NODE_REVIEWER,
            action="REVIEW_PLAN", status="IN_PROGRESS",
        )

        report = run_reviewer_agent(
            project_id=state["project_id"],
            workflow_run_id=config["configurable"]["thread_id"],
            session_factory=config["configurable"]["session_factory"],
            vector_service=config["configurable"].get("vector_service"),
        )
        save_reviewer_report(
            state["project_id"], report,
            session_factory=config["configurable"]["session_factory"],
        )

        _log(
            state, config, agent="Reviewer", stage=NODE_REVIEWER,
            action=f"DECISION_{report.decision}", status="SUCCESS",
            result_count=len(report.revision_instructions),
        )

        return {
            "current_stage": NODE_REVIEWER,
            "reviewer_decision": report.decision,
        }

    except (AgentError, ValueError) as e:
        error_msg = str(e)
        _log(
            state, config, agent="Reviewer", stage=NODE_REVIEWER,
            action="ERROR", status="ERROR", error=error_msg,
        )
        return {"errors": [*state["errors"], error_msg]}


def plan_revision_node(state: ProjectWorkflowState, config: RunnableConfig) -> dict:
    """Planning Agent revision node (Day 13, spec §7.4, §20.1). Re-runs the full planning
    sequence once, with the current Reviewer report's revision_instructions threaded into
    every generation prompt as additional context. The router (routes.py) is the loop-limit
    authority (`revision_count < 1`) — this node just does the work and increments the
    counter.
    """
    from sqlalchemy import select

    from app.agents.planning import run_planning_agent
    from app.agents.runner import AgentError
    from app.models.plan_artifact import PlanArtifactVersion
    from app.schemas.reviewer import ReviewerReport
    from app.tools.project_tools import get_current_plan_version_id

    session_factory = config["configurable"]["session_factory"]
    session = session_factory()
    try:
        version = session.scalar(
            select(PlanArtifactVersion).where(
                PlanArtifactVersion.project_id == state["project_id"],
                PlanArtifactVersion.is_current.is_(True),
            )
        )
        revision_instructions = (
            ReviewerReport.model_validate(version.reviewer_report_json).revision_instructions
            if version and version.reviewer_report_json
            else []
        )
    finally:
        session.close()

    try:
        _log(
            state, config, agent="Planning", stage=NODE_PLAN_REVISION,
            action="REVISE_PLAN", status="IN_PROGRESS",
        )

        run_planning_agent(
            project_id=state["project_id"],
            workflow_run_id=config["configurable"]["thread_id"],
            session_factory=session_factory,
            vector_service=config["configurable"].get("vector_service"),
            revision_instructions=revision_instructions,
        )
        version_id = get_current_plan_version_id(state["project_id"], session_factory=session_factory)

        _log(
            state, config, agent="Planning", stage=NODE_PLAN_REVISION,
            action="REVISE_PLAN", status="SUCCESS",
        )

        return {
            "current_stage": NODE_PLAN_REVISION,
            "plan_version_id": version_id,
            "reviewer_decision": None,
            "revision_count": state["revision_count"] + 1,
        }

    except (AgentError, ValueError) as e:
        error_msg = str(e)
        _log(
            state, config, agent="Planning", stage=NODE_PLAN_REVISION,
            action="ERROR", status="ERROR", error=error_msg,
        )
        return {
            "errors": [*state["errors"], error_msg],
            "revision_count": state["revision_count"] + 1,
        }


def _stub_node_factory(node_name: str):
    agent_name, day = _NOT_IMPLEMENTED[node_name]

    def node(state: ProjectWorkflowState, config: RunnableConfig) -> dict:
        message = f"{agent_name} agent is not implemented yet (ships Day {day})"
        _log(
            state, config, agent=agent_name, stage=node_name,
            action="NOT_IMPLEMENTED", status="ERROR", error=message,
        )
        return {"errors": [*state["errors"], message]}

    return node


def clarification_gate_node(state: ProjectWorkflowState, config: RunnableConfig) -> dict:
    """§11 gate 1. `interrupt()` is the first statement so a resume never re-runs a side
    effect (logging happens only after it returns, i.e. only on resume).
    """
    interrupt({"stage": NODE_CLARIFICATION_GATE, "unresolved_question_ids": state["unresolved_question_ids"]})
    _log(state, config, agent="Workflow", stage=NODE_CLARIFICATION_GATE, action="RESUMED", status="SUCCESS")
    return {"current_stage": NODE_CLARIFICATION_GATE}


def final_gate_node(state: ProjectWorkflowState, config: RunnableConfig) -> dict:
    """§11 gate 2."""
    interrupt({"stage": NODE_FINAL_GATE})
    _log(state, config, agent="Workflow", stage=NODE_FINAL_GATE, action="RESUMED", status="SUCCESS")
    return {"current_stage": NODE_FINAL_GATE}


def stop_error_node(state: ProjectWorkflowState, config: RunnableConfig) -> dict:
    _log(
        state, config, agent="Workflow", stage=NODE_STOP_ERROR,
        action="STOP_WITH_ERROR", status="ERROR", error="; ".join(state["errors"]),
    )
    return {"current_stage": NODE_STOP_ERROR}


def build_graph() -> StateGraph:
    graph = StateGraph(ProjectWorkflowState)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node(NODE_REQUIREMENT_ANALYST, requirement_analyst_node)
    graph.add_node(NODE_PLANNING, planning_node)
    graph.add_node(NODE_REVIEWER, reviewer_node)
    graph.add_node(NODE_PLAN_REVISION, plan_revision_node)
    graph.add_node(NODE_EXPORT, _stub_node_factory(NODE_EXPORT))
    graph.add_node(NODE_CLARIFICATION_GATE, clarification_gate_node)
    graph.add_node(NODE_FINAL_GATE, final_gate_node)
    graph.add_node(NODE_STOP_ERROR, stop_error_node)

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        route_next_node,
        {
            NODE_REQUIREMENT_ANALYST: NODE_REQUIREMENT_ANALYST,
            NODE_CLARIFICATION_GATE: NODE_CLARIFICATION_GATE,
            NODE_PLANNING: NODE_PLANNING,
            NODE_REVIEWER: NODE_REVIEWER,
            NODE_PLAN_REVISION: NODE_PLAN_REVISION,
            NODE_FINAL_GATE: NODE_FINAL_GATE,
            NODE_EXPORT: NODE_EXPORT,
            NODE_STOP_ERROR: NODE_STOP_ERROR,
        },
    )
    # Every specialist/gate node loops back to the supervisor for re-routing; only the
    # two terminal nodes end the graph.
    for name in (
        NODE_REQUIREMENT_ANALYST, NODE_PLANNING, NODE_REVIEWER,
        NODE_PLAN_REVISION, NODE_CLARIFICATION_GATE, NODE_FINAL_GATE,
    ):
        graph.add_edge(name, "supervisor")
    graph.add_edge(NODE_EXPORT, END)
    graph.add_edge(NODE_STOP_ERROR, END)
    return graph


def compile_graph(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    return build_graph().compile(checkpointer=checkpointer)

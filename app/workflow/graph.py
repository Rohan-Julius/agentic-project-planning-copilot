"""LangGraph state graph (Day 7, DESIGN.md §7.1/§7.2, spec §10/§19).

Node bodies for the four specialist agents (`requirement_analyst`, `planning`, `reviewer`,
`plan_revision`) and `export` are stubs — those agents ship on Days 9, 11-13, 13, and 14
respectively (see PROJECT_PLAN.md). A stub records a `WorkflowEvent` and appends to
`state["errors"]`; the router (`route_next_node`) then sends the run straight to
`stop_error` on the very next pass, since any non-empty `errors` is an unconditional
controlled stop. This is what makes the graph safely invokable end-to-end today, without
faking data or looping forever waiting on functionality that doesn't exist yet (see
docs/DAY7_UNDERSTANDING.md decision 1).

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

# (display agent name, day it ships) — PROJECT_PLAN.md.
_NOT_IMPLEMENTED = {
    NODE_REQUIREMENT_ANALYST: ("RequirementAnalyst", 9),
    NODE_PLANNING: ("Planning", 11),
    NODE_REVIEWER: ("Reviewer", 13),
    NODE_PLAN_REVISION: ("Planning", 13),
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
    for name in (NODE_REQUIREMENT_ANALYST, NODE_PLANNING, NODE_REVIEWER, NODE_PLAN_REVISION, NODE_EXPORT):
        graph.add_node(name, _stub_node_factory(name))
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

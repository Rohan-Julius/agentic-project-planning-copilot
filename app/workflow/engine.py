"""Workflow engine (Day 7) — starts/resumes a run against the compiled graph and keeps
the `WorkflowRun` row in sync with the graph's result (§21 run tracking).

`resume_workflow` has no HTTP endpoint yet — `clarifications/approve` (Day 10) and
`plan/approve` (Day 14) will call it once those gates exist. It's built now because
proving the interrupt/resume/checkpoint chain actually works end-to-end is itself a Day 7
deliverable (DESIGN.md §7.5).
"""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.workflow import WorkflowRun
from app.services.vector_service import VectorService
from app.workflow.graph import compile_graph
from app.workflow.state import ProjectWorkflowState

# WorkflowRun.status vocabulary — not fixed by the spec; chosen here (see DAY7_UNDERSTANDING.md).
STATUS_RUNNING = "RUNNING"
STATUS_WAITING_FOR_HUMAN_INPUT = "WAITING_FOR_HUMAN_INPUT"
STATUS_COMPLETED = "COMPLETED"
STATUS_ERROR = "ERROR"

_RECURSION_LIMIT = 50  # defensive backstop; §20.1's real bound is revision_count, not this.


def generate_workflow_run_id() -> str:
    return f"RUN-{uuid.uuid4().hex[:10]}"


def _initial_state(project_id: str) -> ProjectWorkflowState:
    return {
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


def _sync_run(session: Session, run: WorkflowRun, result: dict[str, Any]) -> WorkflowRun:
    if "__interrupt__" in result:
        run.status = STATUS_WAITING_FOR_HUMAN_INPUT
    elif result.get("current_stage") == "export":
        run.status = STATUS_COMPLETED
        run.ended_at = dt.datetime.now(dt.timezone.utc)
    elif result.get("errors"):
        run.status = STATUS_ERROR
        run.ended_at = dt.datetime.now(dt.timezone.utc)
    else:
        run.status = STATUS_RUNNING
    run.revision_count = result.get("revision_count", run.revision_count)
    run.final_approved = result.get("final_approved", run.final_approved)
    session.commit()
    session.refresh(run)
    return run


def _config(
    workflow_run_id: str,
    session_factory: sessionmaker,
    vector_service: VectorService | None,
) -> dict[str, Any]:
    return {
        "configurable": {
            "thread_id": workflow_run_id,
            "session_factory": session_factory,
            # Threaded the same way as session_factory (see docstring below) so agent
            # nodes that call retrieval tools (requirement_analyst, planning, reviewer)
            # hit the test-overridden Qdrant instance instead of the process-wide
            # get_vector_service() singleton. None preserves prior behavior — tools fall
            # back to that singleton themselves when not given one.
            "vector_service": vector_service,
        },
        "recursion_limit": _RECURSION_LIMIT,
    }


def start_workflow(
    session: Session,
    checkpointer: BaseCheckpointSaver,
    project_id: str,
    session_factory: sessionmaker,
    vector_service: VectorService | None = None,
) -> WorkflowRun:
    """`session_factory` must be bound to the same engine as `session` — it's what graph
    nodes use to log `WorkflowEvent` rows mid-run (see graph.py `_log`); passing the
    production `get_sessionmaker()` singleton here instead of a test-overridden one would
    silently write to the wrong database. `vector_service` follows the same rule for
    retrieval-tool calls.
    """
    workflow_run_id = generate_workflow_run_id()
    run = WorkflowRun(workflow_run_id=workflow_run_id, project_id=project_id, status=STATUS_RUNNING)
    session.add(run)
    session.commit()
    session.refresh(run)

    graph = compile_graph(checkpointer)
    result = graph.invoke(
        _initial_state(project_id),
        config=_config(workflow_run_id, session_factory, vector_service),
    )
    return _sync_run(session, run, result)


def get_pending_gate_stage(
    checkpointer: BaseCheckpointSaver,
    workflow_run_id: str,
    session_factory: sessionmaker,
    vector_service: VectorService | None = None,
) -> str | None:
    """The stage name (`NODE_CLARIFICATION_GATE` or `NODE_FINAL_GATE`) of whichever gate is
    currently interrupted, or `None` if the run isn't paused at a gate right now.

    Both gate nodes call `interrupt({"stage": ...})` as their first statement (graph.py),
    so this is the only reliable way to tell *which* gate a WAITING_FOR_HUMAN_INPUT run is
    actually paused at — `WorkflowRun.status` alone can't distinguish them (both gates report
    the same generic status), which previously let `/clarifications/approve` silently resume
    a paused `final_gate` (setting the already-true `clarification_approved` and leaving
    `final_approved` unset, so the run just re-paused at `final_gate` — looked like an
    infinite loop; found live).
    """
    graph = compile_graph(checkpointer)
    config = _config(workflow_run_id, session_factory, vector_service)
    snapshot = graph.get_state(config)
    if not snapshot.interrupts:
        return None
    value = snapshot.interrupts[0].value
    return value.get("stage") if isinstance(value, dict) else None


def resume_workflow(
    session: Session,
    checkpointer: BaseCheckpointSaver,
    workflow_run_id: str,
    resume_value: Any,
    session_factory: sessionmaker,
    vector_service: VectorService | None = None,
    state_patch: dict[str, Any] | None = None,
) -> WorkflowRun:
    """`state_patch` applies a direct state update (via LangGraph's `update_state`) before
    resuming — e.g. clarifications/approve (Day 10) sets `clarification_approved=True`,
    plan/approve (Day 14) will set `final_approved=True`. The gate nodes themselves
    (`clarification_gate_node`/`final_gate_node`) never read the interrupt's resume value,
    so a bare `Command(resume=...)` alone just re-hits the same interrupt forever (see
    test_clarification_gate_interrupts_and_resumes) — the state flag has to be set
    out-of-band first.
    """
    run = session.scalar(select(WorkflowRun).where(WorkflowRun.workflow_run_id == workflow_run_id))
    if run is None:
        raise ValueError(f"Workflow run '{workflow_run_id}' not found")

    graph = compile_graph(checkpointer)
    config = _config(workflow_run_id, session_factory, vector_service)
    if state_patch:
        graph.update_state(config, state_patch)
    result = graph.invoke(Command(resume=resume_value), config=config)
    return _sync_run(session, run, result)

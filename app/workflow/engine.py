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


def _config(workflow_run_id: str, session_factory: sessionmaker) -> dict[str, Any]:
    return {
        "configurable": {"thread_id": workflow_run_id, "session_factory": session_factory},
        "recursion_limit": _RECURSION_LIMIT,
    }


def start_workflow(
    session: Session,
    checkpointer: BaseCheckpointSaver,
    project_id: str,
    session_factory: sessionmaker,
) -> WorkflowRun:
    """`session_factory` must be bound to the same engine as `session` — it's what graph
    nodes use to log `WorkflowEvent` rows mid-run (see graph.py `_log`); passing the
    production `get_sessionmaker()` singleton here instead of a test-overridden one would
    silently write to the wrong database.
    """
    workflow_run_id = generate_workflow_run_id()
    run = WorkflowRun(workflow_run_id=workflow_run_id, project_id=project_id, status=STATUS_RUNNING)
    session.add(run)
    session.commit()
    session.refresh(run)

    graph = compile_graph(checkpointer)
    result = graph.invoke(_initial_state(project_id), config=_config(workflow_run_id, session_factory))
    return _sync_run(session, run, result)


def resume_workflow(
    session: Session,
    checkpointer: BaseCheckpointSaver,
    workflow_run_id: str,
    resume_value: Any,
    session_factory: sessionmaker,
) -> WorkflowRun:
    run = session.scalar(select(WorkflowRun).where(WorkflowRun.workflow_run_id == workflow_run_id))
    if run is None:
        raise ValueError(f"Workflow run '{workflow_run_id}' not found")

    graph = compile_graph(checkpointer)
    result = graph.invoke(Command(resume=resume_value), config=_config(workflow_run_id, session_factory))
    return _sync_run(session, run, result)

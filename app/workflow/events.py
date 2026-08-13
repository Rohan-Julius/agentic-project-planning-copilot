"""Workflow-event logging (Day 7, spec §21) — one `WorkflowEvent` row per node/tool call.

Mirrors the §21 example exactly: `timestamp, project_id, workflow_run_id, agent, stage,
action, tool, status, result_count, duration_ms, error`. Never pass full documents, secrets,
hidden model reasoning, or env values via `error`/`extra` (§21 "do not log").
"""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.models.workflow import WorkflowEvent

if TYPE_CHECKING:
    from sqlalchemy.orm import sessionmaker


def log_event(
    session: Session,
    *,
    workflow_run_id: str,
    project_id: str,
    agent: str,
    stage: str,
    action: str,
    status: str,
    tool: str | None = None,
    result_count: int | None = None,
    duration_ms: int | None = None,
    error: str | None = None,
    extra: dict | None = None,
) -> WorkflowEvent:
    event = WorkflowEvent(
        workflow_run_id=workflow_run_id,
        project_id=project_id,
        agent=agent,
        stage=stage,
        action=action,
        tool=tool,
        status=status,
        result_count=result_count,
        duration_ms=duration_ms,
        error=error,
        extra_json=extra or {},
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def log_tool_call(
    session_factory: "Callable[[], Session] | sessionmaker | None",
    *,
    workflow_run_id: str,
    project_id: str,
    agent: str,
    stage: str,
    tool: str,
) -> None:
    """One `CALL_TOOL` event per real tool invocation inside an agent's own code (spec §16.4
    "tool being called" — previously the schema/model/frontend all supported a `tool` field,
    but nothing in any of the four agents ever actually passed one, so the execution screen
    could never show it). Drop this in immediately after the real tool call it's reporting,
    using the same `session_factory` already in scope there — every agent module already
    receives (`project_id`, `workflow_run_id`, `session_factory`) as parameters, so this needs
    no extra wiring.

    Resolves `None` to the default sessionmaker the same way every function in app/tools/
    already does (`session_factory or get_sessionmaker()`), so callers don't need their own
    fallback. `stage` is the workflow node string (e.g. `NODE_REQUIREMENT_ANALYST` from
    app.workflow.routes), and `tool` is the plain Python function name (e.g.
    "search_project_documents") — the raw name is what's persisted for the audit trail;
    translating it to an English sentence for display is the frontend's job
    (frontend/src/utils/workflowLabels.ts toolLabel()), not this layer's.
    """
    from app.database.session import get_sessionmaker

    resolved_factory = session_factory or get_sessionmaker()
    session = resolved_factory()
    try:
        log_event(
            session,
            workflow_run_id=workflow_run_id,
            project_id=project_id,
            agent=agent,
            stage=stage,
            action="CALL_TOOL",
            status="SUCCESS",
            tool=tool,
        )
    finally:
        session.close()

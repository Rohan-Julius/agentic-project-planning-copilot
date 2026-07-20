"""Workflow-event logging (Day 7, spec §21) — one `WorkflowEvent` row per node/tool call.

Mirrors the §21 example exactly: `timestamp, project_id, workflow_run_id, agent, stage,
action, tool, status, result_count, duration_ms, error`. Never pass full documents, secrets,
hidden model reasoning, or env values via `error`/`extra` (§21 "do not log").
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.workflow import WorkflowEvent


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

"""Workflow run/event read schemas (spec §18, §21)."""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict


class WorkflowRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    workflow_run_id: str
    project_id: str
    status: str
    revision_count: int
    final_approved: bool
    started_at: dt.datetime
    ended_at: dt.datetime | None = None
    # Which gate is actually interrupted right now ("clarification_gate" / "final_gate"),
    # or None if not paused at a gate. Only ever set by /workflow/status (via
    # engine.get_pending_gate_stage, reading the interrupt's own payload) — not by
    # WorkflowRun's ORM columns, and never by the Supervisor's advisory recommendation,
    # which proved unreliable for driving UI navigation (see clarifications/approve and
    # plan/approve's matching gate guard).
    pending_gate: str | None = None


class WorkflowEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    workflow_run_id: str
    timestamp: dt.datetime
    agent: str
    stage: str
    action: str
    tool: str | None = None
    status: str
    result_count: int | None = None
    duration_ms: int | None = None
    error: str | None = None

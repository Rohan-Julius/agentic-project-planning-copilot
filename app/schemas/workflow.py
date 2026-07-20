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

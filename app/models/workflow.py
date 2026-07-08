"""Workflow run + event logging tables (spec §19, §21).

WorkflowEvent mirrors the §21 example event exactly (workflow_run_id, project_id,
agent, action, status, result_count, duration_ms) plus the timestamp/stage/errors the
logging requirements call for. Hidden model reasoning, secrets, and full documents are
never logged here — only safe execution summaries (spec §16.4, §21).
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workflow_run_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.project_id"), index=True
    )
    status: Mapped[str] = mapped_column(String, default="RUNNING")
    revision_count: Mapped[int] = mapped_column(Integer, default=0)
    final_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=lambda: dt.datetime.now(dt.timezone.utc)
    )
    ended_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class WorkflowEvent(Base):
    __tablename__ = "workflow_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workflow_run_id: Mapped[str] = mapped_column(
        String, ForeignKey("workflow_runs.workflow_run_id"), index=True
    )
    project_id: Mapped[str] = mapped_column(String, index=True)
    timestamp: Mapped[dt.datetime] = mapped_column(
        DateTime, default=lambda: dt.datetime.now(dt.timezone.utc)
    )
    agent: Mapped[str] = mapped_column(String)
    stage: Mapped[str] = mapped_column(String, default="")
    action: Mapped[str] = mapped_column(String)
    tool: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String)
    result_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    extra_json: Mapped[dict] = mapped_column(JSON, default=dict)

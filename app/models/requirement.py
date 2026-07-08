"""Requirement + clarification tables (spec §13.1, §13.2).

Top-level columns are indexed for the lookups tools actually need (project_id,
requirement_id, category, classification); nested structures (source_references) are
stored as JSON to avoid over-normalizing for a PoC (see docs/DAY2_UNDERSTANDING.md
point 8). `payload_json` retains the full validated Pydantic payload for fidelity.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RequirementRecord(Base):
    __tablename__ = "requirements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    requirement_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.project_id"), index=True
    )
    title: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String, index=True)
    classification: Mapped[str] = mapped_column(String, index=True)
    confidence: Mapped[float] = mapped_column(default=0.0)
    payload_json: Mapped[dict] = mapped_column(JSON)
    workflow_run_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=lambda: dt.datetime.now(dt.timezone.utc)
    )


class ClarificationQuestionRecord(Base):
    __tablename__ = "clarification_questions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    question_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.project_id"), index=True
    )
    category: Mapped[str] = mapped_column(String, default="")
    priority: Mapped[str] = mapped_column(String, default="Medium")
    status: Mapped[str] = mapped_column(String, default="PENDING", index=True)
    payload_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=lambda: dt.datetime.now(dt.timezone.utc)
    )

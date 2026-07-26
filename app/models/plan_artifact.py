"""Versioned plan artifact storage (spec §13, §22).

Stores one full ProjectPlan JSON snapshot per version rather than fully normalizing
every nested artifact into its own table — matches PoC scope (§19 requires artifacts be
stored in the database, not fully-normalized relational modeling) while still recording
what §22 requires for comparison: timestamp, model, prompt version, previous vs new
output. A full visual diff is explicitly optional per spec and is not implemented.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PlanArtifactVersion(Base):
    __tablename__ = "plan_artifact_versions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    version_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey("projects.project_id"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer)
    plan_json: Mapped[dict] = mapped_column(JSON)
    model: Mapped[str] = mapped_column(String, default="")
    prompt_version: Mapped[str] = mapped_column(String, default="")
    reviewer_decision: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewer_report_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    generated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=lambda: dt.datetime.now(dt.timezone.utc)
    )

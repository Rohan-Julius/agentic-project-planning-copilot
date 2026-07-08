"""Project table (spec §16.2)."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ProjectRecord(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String, default="")
    business_domain: Mapped[str] = mapped_column(String, default="")
    # Fixed to "agile_scrum" per project decision — see app.schemas.enums.Methodology.
    methodology: Mapped[str] = mapped_column(String, default="agile_scrum")
    expected_duration_weeks: Mapped[int | None] = mapped_column(nullable=True)
    team_composition: Mapped[str] = mapped_column(String, default="")
    target_platforms: Mapped[list] = mapped_column(JSON, default=list)
    technology_constraints: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String, default="CREATED")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=lambda: dt.datetime.now(dt.timezone.utc)
    )

"""Project CRUD (spec §16.2, §18)."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import ProjectRecord
from app.schemas.project import ProjectCreate


def generate_project_id() -> str:
    return f"proj_{uuid.uuid4().hex[:12]}"


def create_project(session: Session, data: ProjectCreate) -> ProjectRecord:
    project = ProjectRecord(
        project_id=generate_project_id(),
        name=data.name,
        description=data.description,
        business_domain=data.business_domain,
        methodology=data.methodology.value,
        expected_duration_weeks=data.expected_duration_weeks,
        team_composition=data.team_composition,
        target_platforms=data.target_platforms,
        technology_constraints=data.technology_constraints,
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def list_projects(session: Session) -> list[ProjectRecord]:
    return list(session.scalars(select(ProjectRecord)))


def get_project(session: Session, project_id: str) -> ProjectRecord | None:
    return session.scalar(
        select(ProjectRecord).where(ProjectRecord.project_id == project_id)
    )

"""Requirements endpoints (spec §18, §9.4).

Exposes extracted requirements from the Requirement Analyst Agent.
Filters by project_id for isolation (spec §12.3, §20.4).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends

from app.database.session import get_session
from app.models.requirement import RequirementRecord
from app.schemas.requirement import RequirementRead

router = APIRouter(prefix="/projects/{project_id}/requirements", tags=["requirements"])


@router.get("", response_model=list[RequirementRead])
def get_requirements(
    project_id: str,
    session: Session = Depends(get_session),
) -> list[RequirementRead]:
    """Retrieve all requirements for a project (spec §9.4, §18).

    Filters by project_id to prevent cross-project data leakage (§12.3, §20.4).
    Returns all requirements extracted by the Requirement Analyst Agent for this project,
    in creation order.

    Args:
        project_id: The project ID to filter by
        session: Database session (injected)

    Returns:
        List of requirements for the project (may be empty)
    """
    requirements = session.scalars(
        select(RequirementRecord)
        .where(RequirementRecord.project_id == project_id)
        .order_by(RequirementRecord.created_at)
    ).all()

    return [RequirementRead.model_validate(req) for req in requirements]

"""Requirements endpoints (spec §16.6, §18, §9.4).

Exposes extracted requirements from the Requirement Analyst Agent.
Filters by project_id for isolation (spec §12.3, §20.4).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException

from app.database.session import get_session
from app.models.requirement import RequirementRecord
from app.services import project_service
from app.schemas.requirement import RequirementRead

router = APIRouter(prefix="/projects/{project_id}/requirements", tags=["requirements"])


def _require_project(session: Session, project_id: str) -> None:
    if project_service.get_project(session, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


def _to_read(record: RequirementRecord) -> RequirementRead:
    """`description` and `source_references` live inside `payload_json` (the full original
    `Requirement` dump), not as their own columns — `.get(..., default)` so a payload that
    predates a field being added here still reads back instead of 500ing.
    """
    payload = record.payload_json or {}
    return RequirementRead(
        requirement_id=record.requirement_id,
        project_id=record.project_id,
        title=record.title,
        description=payload.get("description", ""),
        category=record.category,
        classification=record.classification,
        confidence=record.confidence,
        source_references=payload.get("source_references", []),
        workflow_run_id=record.workflow_run_id,
        created_at=record.created_at,
    )


@router.get("", response_model=list[RequirementRead])
def get_requirements(
    project_id: str,
    session: Session = Depends(get_session),
) -> list[RequirementRead]:
    """Retrieve all requirements for a project (spec §16.6, §9.4, §18).

    Filters by project_id to prevent cross-project data leakage (§12.3, §20.4).
    Returns all requirements extracted by the Requirement Analyst Agent for this project,
    in creation order.

    Args:
        project_id: The project ID to filter by
        session: Database session (injected)

    Returns:
        List of requirements for the project (may be empty)
    """
    _require_project(session, project_id)
    requirements = session.scalars(
        select(RequirementRecord)
        .where(RequirementRecord.project_id == project_id)
        .order_by(RequirementRecord.created_at)
    ).all()

    return [_to_read(req) for req in requirements]

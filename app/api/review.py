"""Reviewer report read endpoint (spec §13.12, §18)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.models.plan_artifact import PlanArtifactVersion
from app.schemas.reviewer import ReviewerReport
from app.services import project_service

router = APIRouter(prefix="/projects/{project_id}/review", tags=["review"])


def _require_project(session: Session, project_id: str) -> None:
    if project_service.get_project(session, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.get("", response_model=ReviewerReport)
def get_review(project_id: str, session: Session = Depends(get_session)) -> ReviewerReport:
    """Return the Reviewer Agent's report for the current plan version (spec §13.12, §18).
    404 if no review has run yet.
    """
    _require_project(session, project_id)
    version = session.scalar(
        select(PlanArtifactVersion).where(
            PlanArtifactVersion.project_id == project_id,
            PlanArtifactVersion.is_current.is_(True),
        )
    )
    if version is None or version.reviewer_report_json is None:
        raise HTTPException(status_code=404, detail=f"No review generated yet for project '{project_id}'")
    return ReviewerReport.model_validate(version.reviewer_report_json)

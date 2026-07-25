"""Plan read endpoint (spec §18, §9.7)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.models.plan_artifact import PlanArtifactVersion
from app.schemas.planning import ProjectPlan
from app.services import project_service

router = APIRouter(prefix="/projects/{project_id}/plan", tags=["plan"])


def _require_project(session: Session, project_id: str) -> None:
    if project_service.get_project(session, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.get("", response_model=ProjectPlan)
def get_plan(project_id: str, session: Session = Depends(get_session)) -> ProjectPlan:
    """Return the current plan version for a project (spec §9.7, §18). 404 if no plan has
    been generated yet.
    """
    _require_project(session, project_id)
    version = session.scalar(
        select(PlanArtifactVersion).where(
            PlanArtifactVersion.project_id == project_id,
            PlanArtifactVersion.is_current.is_(True),
        )
    )
    if version is None:
        raise HTTPException(status_code=404, detail=f"No plan generated yet for project '{project_id}'")
    return ProjectPlan.model_validate(version.plan_json)

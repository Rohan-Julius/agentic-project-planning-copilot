"""Project endpoints (spec §18)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.schemas.project import ProjectCreate, ProjectRead
from app.services import project_service

router = APIRouter(prefix="/projects", tags=["projects"])


def _to_read(project) -> ProjectRead:
    return ProjectRead(
        project_id=project.project_id,
        name=project.name,
        description=project.description,
        business_domain=project.business_domain,
        methodology=project.methodology,
        expected_duration_weeks=project.expected_duration_weeks,
        team_composition=project.team_composition,
        target_platforms=project.target_platforms,
        technology_constraints=project.technology_constraints,
        status=project.status,
    )


@router.post("", response_model=ProjectRead, status_code=201)
def create_project(data: ProjectCreate, session: Session = Depends(get_session)):
    project = project_service.create_project(session, data)
    return _to_read(project)


@router.get("", response_model=list[ProjectRead])
def list_projects(session: Session = Depends(get_session)):
    return [_to_read(p) for p in project_service.list_projects(session)]


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: str, session: Session = Depends(get_session)):
    project = project_service.get_project(session, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return _to_read(project)

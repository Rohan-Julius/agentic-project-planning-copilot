"""Project endpoints (spec §18)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database.session import get_session
from app.schemas.project import ProjectCreate, ProjectRead
from app.services import document_service, project_service
from app.services.embedding_service import EmbeddingService, get_embedding_service
from app.services.indexing_service import IndexResult, index_documents
from app.services.vector_service import VectorService, get_vector_service

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


@router.post("/{project_id}/index", response_model=IndexResult)
def index_project_documents(
    project_id: str,
    force: bool = False,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    embedder: EmbeddingService = Depends(get_embedding_service),
    vector_service: VectorService = Depends(get_vector_service),
):
    """§18 `POST /projects/{id}/index` — parse -> chunk -> embed -> upsert (DESIGN.md §6)."""
    if project_service.get_project(session, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    documents = document_service.list_documents(session, project_id)
    return index_documents(
        session,
        settings,
        embedder,
        vector_service,
        settings.qdrant_project_collection,
        documents,
        force=force,
    )

"""Document endpoints (spec §18, §16.3)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database.session import get_session
from app.schemas.document import DocumentRead, DocumentTextCreate
from app.services import document_service, project_service
from app.services.document_service import UnsupportedFormatError

router = APIRouter(prefix="/projects/{project_id}/documents", tags=["documents"])


def _to_read(document) -> DocumentRead:
    return DocumentRead(
        document_id=document.document_id,
        project_id=document.project_id,
        document_name=document.document_name,
        document_type=document.document_type,
        source_type=document.source_type,
        document_version=document.document_version,
        status=document.status,
    )


def _require_project(session: Session, project_id: str) -> None:
    if project_service.get_project(session, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.post("", response_model=DocumentRead, status_code=201)
async def upload_document(
    project_id: str,
    file: UploadFile,
    document_type: str = "",
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    _require_project(session, project_id)
    content = await file.read()
    try:
        document = document_service.save_uploaded_document(
            session, settings, project_id, file.filename, content, document_type
        )
    except UnsupportedFormatError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _to_read(document)


@router.post("/text", response_model=DocumentRead, status_code=201)
def create_text_document(
    project_id: str,
    data: DocumentTextCreate,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    _require_project(session, project_id)
    try:
        document = document_service.save_text_document(
            session,
            settings,
            project_id,
            data.document_name,
            data.content,
            data.document_type,
        )
    except UnsupportedFormatError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _to_read(document)


@router.get("", response_model=list[DocumentRead])
def list_documents(project_id: str, session: Session = Depends(get_session)):
    _require_project(session, project_id)
    return [_to_read(d) for d in document_service.list_documents(session, project_id)]


@router.delete("/{document_id}", status_code=204)
def delete_document(
    project_id: str, document_id: str, session: Session = Depends(get_session)
):
    _require_project(session, project_id)
    if not document_service.delete_document(session, project_id, document_id):
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")

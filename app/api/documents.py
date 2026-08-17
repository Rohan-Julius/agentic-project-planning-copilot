"""Document endpoints (spec §18, §16.3)."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database.session import get_session
from app.schemas.document import ChunkPayload, DocumentRead, DocumentTextCreate, ParsedDocument
from app.services import document_service, project_service
from app.services.document_service import DocumentParsingError, UnsupportedFormatError
from app.services.vector_service import VectorService, get_vector_service

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
    document_type: str = Form(""),
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
    project_id: str,
    document_id: str,
    session: Session = Depends(get_session),
    vector_service: VectorService = Depends(get_vector_service),
):
    _require_project(session, project_id)
    if not document_service.delete_document(session, project_id, document_id, vector_service):
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")


@router.get("/{document_id}/text", response_model=ParsedDocument)
def get_document_text(
    project_id: str,
    document_id: str,
    session: Session = Depends(get_session),
):
    """§16.3 "viewing extracted text" — re-parses the stored file on demand rather than
    persisting a second copy: the file on disk is already the source of truth, parsing is
    deterministic and cheap, and a cached copy could silently drift from it.
    """
    _require_project(session, project_id)
    document = document_service.get_document(session, project_id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")
    file_path = Path(document.file_path)
    try:
        return document_service.parse_document(file_path, file_path.suffix, document_id)
    except DocumentParsingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{document_id}/chunks", response_model=list[ChunkPayload])
def get_document_chunks(
    project_id: str,
    document_id: str,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    vector_service: VectorService = Depends(get_vector_service),
):
    """§16.3 "viewing chunks" — the chunks actually stored for retrieval, read straight
    from Qdrant (chunk text is never duplicated into SQLite — see `DocumentChunkMeta`).
    An empty list means "not indexed yet", not an error.
    """
    _require_project(session, project_id)
    document = document_service.get_document(session, project_id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")
    return vector_service.list_by_document(
        settings.qdrant_project_collection, project_id, document_id
    )

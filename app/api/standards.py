"""Organizational-knowledge document endpoints — the org-side mirror of `app/api/documents.py`.

Not part of DESIGN.md's original §18 endpoint list; added on Day 6 alongside
`search_company_standards` because no earlier day built an ingestion path for
`organizational_knowledge` (see DAY6_UNDERSTANDING.md's "scope decision" section). Same shape
as project documents — upload, text input, list, delete, index — just unscoped by project.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database.session import get_session
from app.schemas.document import DocumentRead, DocumentTextCreate
from app.services import document_service
from app.services.document_service import UnsupportedFormatError
from app.services.embedding_service import EmbeddingService, get_embedding_service
from app.services.indexing_service import IndexResult, index_documents
from app.services.vector_service import VectorService, get_vector_service

router = APIRouter(prefix="/organizational-documents", tags=["organizational-documents"])


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


@router.post("", response_model=DocumentRead, status_code=201)
async def upload_organizational_document(
    file: UploadFile,
    document_type: str = Form(""),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    content = await file.read()
    try:
        document = document_service.save_uploaded_document(
            session,
            settings,
            None,
            file.filename,
            content,
            document_type,
            source_type="organizational",
        )
    except UnsupportedFormatError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _to_read(document)


@router.post("/text", response_model=DocumentRead, status_code=201)
def create_organizational_text_document(
    data: DocumentTextCreate,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    try:
        document = document_service.save_text_document(
            session,
            settings,
            None,
            data.document_name,
            data.content,
            data.document_type,
            source_type="organizational",
        )
    except UnsupportedFormatError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _to_read(document)


@router.get("", response_model=list[DocumentRead])
def list_organizational_documents(session: Session = Depends(get_session)):
    return [_to_read(d) for d in document_service.list_organizational_documents(session)]


@router.delete("/{document_id}", status_code=204)
def delete_organizational_document(
    document_id: str,
    session: Session = Depends(get_session),
    vector_service: VectorService = Depends(get_vector_service),
):
    if not document_service.delete_organizational_document(session, document_id, vector_service):
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")


@router.post("/index", response_model=IndexResult)
def index_organizational_documents(
    force: bool = False,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    embedder: EmbeddingService = Depends(get_embedding_service),
    vector_service: VectorService = Depends(get_vector_service),
):
    documents = document_service.list_organizational_documents(session)
    return index_documents(
        session,
        settings,
        embedder,
        vector_service,
        settings.qdrant_org_collection,
        documents,
        force=force,
    )

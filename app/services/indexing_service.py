"""`POST .../index` pipeline (Day 6, DESIGN.md §6, spec §18) — parse -> chunk -> embed ->
upsert. Deterministic; no LLM reasoning.

Idempotent by construction (see DAY6_UNDERSTANDING.md decision 6): indexing a document always
clears its existing Qdrant points + `document_chunk_meta` rows first, whether this is the first
index or a re-index, so a re-chunk that yields fewer chunks than before never leaves orphaned
trailing chunks under stale `{document_id}-CH-{seq:03d}` ids.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.document import DocumentRecord
from app.services import document_service
from app.services.chunking_service import chunk_document, embedding_text
from app.services.document_service import DocumentParsingError
from app.services.embedding_service import EmbeddingService
from app.services.vector_service import VectorService

INDEXED_STATUS = "INDEXED"
INDEX_ERROR_STATUS = "INDEX_ERROR"


class IndexResult(BaseModel):
    indexed_document_ids: list[str] = []
    chunk_count: int = 0
    errors: dict[str, str] = {}


def index_documents(
    session: Session,
    settings: Settings,
    embedder: EmbeddingService,
    vector_service: VectorService,
    collection: str,
    documents: list[DocumentRecord],
    force: bool = False,
) -> IndexResult:
    result = IndexResult()
    for document in documents:
        if document.status == INDEXED_STATUS and not force:
            continue
        try:
            extension = Path(document.file_path).suffix
            parsed = document_service.parse_document(
                Path(document.file_path), extension, document.document_id
            )
            chunks = chunk_document(document, parsed, embedder)

            # Clear any previous version of this document's chunks first (decision 6).
            vector_service.delete_by_document(collection, document.document_id)
            session.query(document_service.DocumentChunkMeta).filter(
                document_service.DocumentChunkMeta.document_id == document.document_id
            ).delete()

            if chunks:
                vectors = embedder.embed([embedding_text(chunk) for chunk in chunks])
                vector_service.upsert_chunks(collection, chunks, vectors)
                document_service.save_chunk_meta(session, chunks)

            document.status = INDEXED_STATUS
            session.commit()
            result.indexed_document_ids.append(document.document_id)
            result.chunk_count += len(chunks)
        except DocumentParsingError as exc:
            document.status = INDEX_ERROR_STATUS
            session.commit()
            result.errors[document.document_id] = str(exc)
    return result

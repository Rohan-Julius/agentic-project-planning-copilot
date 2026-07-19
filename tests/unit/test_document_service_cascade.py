"""Delete cascade tests (Day 6, spec §20.4): deleting a document must remove its Qdrant
points AND its `document_chunk_meta` rows, not just the SQLite `DocumentRecord`.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from qdrant_client import QdrantClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.models.base import Base
from app.models.document import DocumentChunkMeta
from app.services import document_service, project_service
from app.services.chunking_service import chunk_document, embedding_text
from app.services.document_service import parse_document
from app.services.embedding_service import EmbeddingService
from app.services.vector_service import VectorService
from app.schemas.project import ProjectCreate


@pytest.fixture
def session(tmp_path):
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


@pytest.fixture
def settings(tmp_path):
    return Settings(data_dir=tmp_path / "data")


def test_delete_document_cascades_to_qdrant_and_chunk_meta(session, settings):
    project = project_service.create_project(session, ProjectCreate(name="Leave Management"))
    document = document_service.save_uploaded_document(
        session, settings, project.project_id, "spec.txt", b"Payments require 3D-secure.",
    )

    embedder = EmbeddingService()
    parsed = parse_document(Path(document.file_path), ".txt", document.document_id)
    chunks = chunk_document(document, parsed, embedder)
    vectors = embedder.embed([embedding_text(c) for c in chunks])

    vector_service = VectorService(client=QdrantClient(location=":memory:"))
    vector_service.upsert_chunks("project_knowledge", chunks, vectors)
    document_service.save_chunk_meta(session, chunks)

    assert session.scalar(
        select(DocumentChunkMeta).where(DocumentChunkMeta.document_id == document.document_id)
    )
    assert vector_service.search(
        "project_knowledge", vectors[0], query_filter=None, top_k=10
    )

    deleted = document_service.delete_document(
        session, project.project_id, document.document_id, vector_service
    )

    assert deleted is True
    assert (
        session.scalar(
            select(DocumentChunkMeta).where(DocumentChunkMeta.document_id == document.document_id)
        )
        is None
    )
    assert vector_service.search("project_knowledge", vectors[0], query_filter=None, top_k=10) == []

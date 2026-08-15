"""Indexing pipeline tests (Day 6/17, spec §18 POST .../index, §25 negatives) — real parser,
real chunker, real embedder, in-memory Qdrant. No mocks: proves a corrupted/empty document
degrades to a per-document error (INDEX_ERROR_STATUS) instead of crashing the whole batch,
which app/api/projects.py::index_project_documents relies on to keep working documents
searchable even when one upload was bad.
"""
from __future__ import annotations

import pytest
from qdrant_client import QdrantClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.models.base import Base
from app.models.document import DocumentRecord
from app.services.embedding_service import EmbeddingService
from app.services.indexing_service import INDEX_ERROR_STATUS, INDEXED_STATUS, index_documents
from app.services.vector_service import VectorService


@pytest.fixture(scope="module")
def embedder():
    return EmbeddingService()


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _document(document_id, project_id, file_path) -> DocumentRecord:
    return DocumentRecord(
        document_id=document_id,
        project_id=project_id,
        document_name=file_path.name,
        document_type="business_requirement",
        source_type="project",
        file_path=str(file_path),
        document_version="1.0",
    )


def test_corrupted_document_mid_batch_does_not_block_the_rest(
    tmp_path, embedder, session_factory
):
    good_path_1 = tmp_path / "good1.txt"
    good_path_1.write_text("The system shall allow employees to request leave.")
    corrupted_path = tmp_path / "bad.pdf"
    corrupted_path.write_bytes(b"not a real pdf file")
    good_path_2 = tmp_path / "good2.txt"
    good_path_2.write_text("Managers shall approve or reject leave requests.")

    session = session_factory()
    session.add_all(
        [
            _document("doc_good_1", "proj_batch", good_path_1),
            _document("doc_bad", "proj_batch", corrupted_path),
            _document("doc_good_2", "proj_batch", good_path_2),
        ]
    )
    session.commit()
    documents = session.query(DocumentRecord).all()

    vector_service = VectorService(client=QdrantClient(location=":memory:"))
    settings = Settings(_env_file=None, DATA_DIR=str(tmp_path))

    result = index_documents(
        session, settings, embedder, vector_service, "project_knowledge", documents
    )

    assert result.indexed_document_ids == ["doc_good_1", "doc_good_2"]
    assert result.chunk_count > 0
    assert set(result.errors.keys()) == {"doc_bad"}

    by_id = {d.document_id: d for d in session.query(DocumentRecord).all()}
    assert by_id["doc_good_1"].status == INDEXED_STATUS
    assert by_id["doc_good_2"].status == INDEXED_STATUS
    assert by_id["doc_bad"].status == INDEX_ERROR_STATUS


def test_empty_document_is_recorded_as_index_error_not_a_crash(
    tmp_path, embedder, session_factory
):
    empty_path = tmp_path / "empty.txt"
    empty_path.write_text("")

    session = session_factory()
    session.add(_document("doc_empty", "proj_empty", empty_path))
    session.commit()
    documents = session.query(DocumentRecord).all()

    vector_service = VectorService(client=QdrantClient(location=":memory:"))
    settings = Settings(_env_file=None, DATA_DIR=str(tmp_path))

    result = index_documents(
        session, settings, embedder, vector_service, "project_knowledge", documents
    )

    assert result.indexed_document_ids == []
    assert "doc_empty" in result.errors
    assert session.get(DocumentRecord, documents[0].id).status == INDEX_ERROR_STATUS

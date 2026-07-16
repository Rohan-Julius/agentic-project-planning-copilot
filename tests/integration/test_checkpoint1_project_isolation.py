"""Checkpoint 1 (DESIGN.md §5.4): full parse -> chunk -> embed -> upsert -> search
pipeline, across two projects, proving retrieval never leaks across project_id.
Real services throughout (real parser, real tokenizer/embedding model, real
qdrant-client in-memory backend) — no mocks.
"""
from __future__ import annotations

from qdrant_client import QdrantClient

from app.models.document import DocumentRecord
from app.schemas.document import ParsedBlock, ParsedDocument
from app.services.chunking_service import chunk_document, embedding_text
from app.services.embedding_service import EmbeddingService
from app.services.vector_service import VectorService


def _document(project_id: str, document_id: str) -> DocumentRecord:
    return DocumentRecord(
        document_id=document_id,
        project_id=project_id,
        document_name="requirements.pdf",
        document_type="business_requirement",
        source_type="project",
        file_path="/tmp/x",
        document_version="1.0",
    )


def _parsed(document_id: str, topic_sentence: str) -> ParsedDocument:
    return ParsedDocument(
        document_id=document_id,
        blocks=[
            ParsedBlock(
                text="1. Payment Processing",
                heading_level=1,
                section_hierarchy_path="1. Payment Processing",
            ),
            ParsedBlock(text=topic_sentence, section_hierarchy_path="1. Payment Processing"),
        ],
    )


def test_checkpoint1_project_isolated_retrieval():
    embedder = EmbeddingService()
    vector_service = VectorService(client=QdrantClient(location=":memory:"))

    project_a = _document("proj_a", "doc_a1")
    project_b = _document("proj_b", "doc_b1")
    chunks_a = chunk_document(
        project_a, _parsed("doc_a1", "Project A requires 3D-secure card verification."), embedder
    )
    chunks_b = chunk_document(
        project_b, _parsed("doc_b1", "Project B requires PayPal wallet integration."), embedder
    )

    for document, chunks in ((project_a, chunks_a), (project_b, chunks_b)):
        vectors = embedder.embed([embedding_text(c) for c in chunks])
        vector_service.upsert_chunks("project_knowledge", chunks, vectors)

    query_vector = embedder.embed_query("What does the payment flow require?")

    results_a = vector_service.search_project(
        "project_knowledge", project_id="proj_a", query_vector=query_vector, top_k=10
    )
    results_b = vector_service.search_project(
        "project_knowledge", project_id="proj_b", query_vector=query_vector, top_k=10
    )

    assert results_a and all(r.payload["project_id"] == "proj_a" for r in results_a)
    assert results_b and all(r.payload["project_id"] == "proj_b" for r in results_b)
    assert {r.payload["chunk_id"] for r in results_a}.isdisjoint(
        {r.payload["chunk_id"] for r in results_b}
    )

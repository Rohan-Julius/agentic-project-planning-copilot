"""Retrieval tool tests (spec §9.1, §9.2, §9.10, §20.4) — real embedder, in-memory Qdrant."""
from __future__ import annotations

import inspect

from qdrant_client import QdrantClient

from app.schemas.document import ChunkPayload
from app.services.embedding_service import EmbeddingService
from app.services.vector_service import VectorService
from app.tools.retrieval_tools import (
    find_supporting_evidence,
    search_company_standards,
    search_project_documents,
)


def _chunk(chunk_id, project_id, text, document_type="", source_type="project") -> ChunkPayload:
    return ChunkPayload(
        chunk_id=chunk_id,
        project_id=project_id,
        document_id=chunk_id.rsplit("-CH-", 1)[0],
        document_name="doc.pdf",
        document_type=document_type,
        source_type=source_type,
        document_version="1.0",
        text=text,
        page_number=1,
        section="Section",
        section_hierarchy_path="Section",
    )


def _services():
    return VectorService(client=QdrantClient(location=":memory:")), EmbeddingService()


def test_search_project_documents_never_returns_another_project():
    vector_service, embedder = _services()
    embed_vectors = embedder.embed(
        ["Project A requires 3D-secure card verification.", "Project B requires PayPal wallet."]
    )
    vector_service.upsert_chunks(
        "project_knowledge",
        [
            _chunk("doc_a-CH-001", "proj_a", "Project A requires 3D-secure card verification."),
            _chunk("doc_b-CH-001", "proj_b", "Project B requires PayPal wallet."),
        ],
        embed_vectors,
    )

    results = search_project_documents(
        "proj_a", "payment flow requirement", vector_service=vector_service, embedder=embedder
    )

    assert results and all(r.project_id == "proj_a" for r in results)


def test_search_project_documents_requires_project_id():
    params = inspect.signature(search_project_documents).parameters
    assert "project_id" in params
    assert params["project_id"].default is inspect.Parameter.empty


def test_search_company_standards_only_queries_organizational_knowledge():
    vector_service, embedder = _services()
    project_chunk = _chunk("doc_a-CH-001", "proj_a", "Project-specific payment requirement.")
    org_chunk = _chunk(
        "org-CH-001", None, "Definition of Done requires code review.",
        document_type="Definition of Done", source_type="organizational",
    )
    vectors = embedder.embed([project_chunk.text, org_chunk.text])
    vector_service.upsert_chunks("project_knowledge", [project_chunk], [vectors[0]])
    vector_service.upsert_chunks("organizational_knowledge", [org_chunk], [vectors[1]])

    results = search_company_standards(
        "definition of done", vector_service=vector_service, embedder=embedder
    )

    assert results
    assert all(r.source_type == "organizational" for r in results)
    assert all(r.chunk_id != "doc_a-CH-001" for r in results)


def test_search_company_standards_category_filters_on_document_type():
    vector_service, embedder = _services()
    chunks = [
        _chunk("org-CH-001", None, "Security checklist: encrypt data at rest.",
               document_type="Security", source_type="organizational"),
        _chunk("org-CH-002", None, "Estimation guidance: use story points.",
               document_type="Estimation", source_type="organizational"),
    ]
    vectors = embedder.embed([c.text for c in chunks])
    vector_service.upsert_chunks("organizational_knowledge", chunks, vectors)

    results = search_company_standards(
        "guidance", category="Estimation", vector_service=vector_service, embedder=embedder
    )

    assert results and all(r.document_type == "Estimation" for r in results)


def test_find_supporting_evidence_is_project_filtered():
    vector_service, embedder = _services()
    chunks = [
        _chunk("doc_a-CH-001", "proj_a", "Data must be retained for one year."),
        _chunk("doc_b-CH-001", "proj_b", "Data must be retained for seven years."),
    ]
    vectors = embedder.embed([c.text for c in chunks])
    vector_service.upsert_chunks("project_knowledge", chunks, vectors)

    results = find_supporting_evidence(
        "proj_a", "data retention period", vector_service=vector_service, embedder=embedder
    )

    assert results and all(r.project_id == "proj_a" for r in results)


def test_deleted_document_is_no_longer_retrieved():
    vector_service, embedder = _services()
    chunk = _chunk("doc_a-CH-001", "proj_a", "Project A requires 3D-secure card verification.")
    vector_service.upsert_chunks("project_knowledge", [chunk], embedder.embed([chunk.text]))
    assert search_project_documents(
        "proj_a", "card verification", vector_service=vector_service, embedder=embedder
    )

    vector_service.delete_by_document("project_knowledge", "doc_a")

    assert not search_project_documents(
        "proj_a", "card verification", vector_service=vector_service, embedder=embedder
    )

"""Hybrid retrieval tests (Day 6, DESIGN.md §6.1) — real embedder, in-memory Qdrant, no mocks."""
from __future__ import annotations

from qdrant_client import QdrantClient

from app.schemas.document import ChunkPayload
from app.services.embedding_service import EmbeddingService
from app.services.retrieval_service import _rrf_fuse, hybrid_search
from app.services.vector_service import VectorService


def _chunk(chunk_id, project_id, text, document_id="doc_1", document_type="") -> ChunkPayload:
    return ChunkPayload(
        chunk_id=chunk_id,
        project_id=project_id,
        document_id=document_id,
        document_name="requirements.pdf",
        document_type=document_type,
        source_type="project",
        document_version="1.0",
        text=text,
        page_number=1,
        section="Payment Processing",
        section_hierarchy_path="3. Functional > 3.2 Payment Processing",
    )


def _seed(vector_service, embedder, collection, chunks):
    vectors = embedder.embed([c.text for c in chunks])
    vector_service.upsert_chunks(collection, chunks, vectors)


# --- RRF math (pure) -----------------------------------------------------------------


def test_rrf_fuse_sums_reciprocal_rank_across_lists():
    dense_rank = ["a", "b", "c"]
    bm25_rank = ["b", "a", "c"]

    fused = _rrf_fuse([dense_rank, bm25_rank], k=60)

    assert fused["a"] == 1 / 61 + 1 / 62
    assert fused["b"] == 1 / 62 + 1 / 61
    assert fused["c"] == 1 / 63 + 1 / 63
    # "a" and "b" tie (same two ranks, swapped) and both beat "c".
    assert fused["a"] == fused["b"] > fused["c"]


def test_rrf_fuse_a_chunk_only_in_one_list_still_scores():
    fused = _rrf_fuse([["only_dense"], ["only_bm25"]], k=60)

    assert fused == {"only_dense": 1 / 61, "only_bm25": 1 / 61}


# --- hybrid_search (real embedder + in-memory Qdrant) ---------------------------------


def test_hybrid_search_empty_corpus_returns_empty_list():
    vector_service = VectorService(client=QdrantClient(location=":memory:"))
    embedder = EmbeddingService()

    results = hybrid_search(
        vector_service.client, "project_knowledge", embedder, "anything", project_id="proj_a"
    )

    assert results == []


def test_hybrid_search_respects_top_k():
    vector_service = VectorService(client=QdrantClient(location=":memory:"))
    embedder = EmbeddingService()
    chunks = [
        _chunk(f"doc_1-CH-{i:03d}", "proj_a", f"Payment requirement number {i}.")
        for i in range(6)
    ]
    _seed(vector_service, embedder, "project_knowledge", chunks)

    results = hybrid_search(
        vector_service.client,
        "project_knowledge",
        embedder,
        "payment requirement",
        top_k=3,
        project_id="proj_a",
    )

    assert len(results) == 3
    for result in results:
        assert 0.0 <= result.similarity_score <= 1.0 + 1e-6
        assert result.project_id == "proj_a"


def test_hybrid_search_project_filter_excludes_other_projects():
    vector_service = VectorService(client=QdrantClient(location=":memory:"))
    embedder = EmbeddingService()
    _seed(
        vector_service,
        embedder,
        "project_knowledge",
        [_chunk("doc_a-CH-001", "proj_a", "Project A requires 3D-secure card verification.")],
    )
    _seed(
        vector_service,
        embedder,
        "project_knowledge",
        [_chunk("doc_b-CH-001", "proj_b", "Project B requires PayPal wallet integration.")],
    )

    results = hybrid_search(
        vector_service.client,
        "project_knowledge",
        embedder,
        "What does the payment flow require?",
        project_id="proj_a",
    )

    assert results and all(r.project_id == "proj_a" for r in results)


def test_hybrid_search_document_types_filter():
    vector_service = VectorService(client=QdrantClient(location=":memory:"))
    embedder = EmbeddingService()
    _seed(
        vector_service,
        embedder,
        "project_knowledge",
        [
            _chunk("doc_a-CH-001", "proj_a", "Functional requirement about login.", document_type="business_requirement"),
            _chunk("doc_a-CH-002", "proj_a", "Meeting note about login timing.", document_type="meeting_notes"),
        ],
    )

    results = hybrid_search(
        vector_service.client,
        "project_knowledge",
        embedder,
        "login",
        project_id="proj_a",
        document_types=["meeting_notes"],
    )

    assert results and all(r.document_type == "meeting_notes" for r in results)

"""Hybrid retrieval (Day 6, DESIGN.md §6.1) — deterministic, no LLM reasoning.

Pipeline: metadata filter (project_id mandatory for project search, §12.3/§20.4) -> dense
search + BM25 over the same scrolled candidate set -> Reciprocal Rank Fusion (RRF, k=60) ->
top-K chunks with full provenance. See docs/DAY6_UNDERSTANDING.md for the two decisions that
depart from DESIGN.md's speculative sketch (no cross-request BM25 cache; dense scores computed
locally from the same scroll instead of a second Qdrant ANN query).
"""
from __future__ import annotations

import re

from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue
from rank_bm25 import BM25Okapi

from app.schemas.document import RetrievedChunk
from app.services.embedding_service import EmbeddingService

RRF_K = 60
_SCROLL_LIMIT = 10_000  # PoC scale: a project's/org's full chunk corpus, not a paged subset.

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _scroll_corpus(
    client: QdrantClient,
    collection: str,
    project_id: str | None,
    document_types: list[str] | None,
) -> list[tuple[dict, list[float]]]:
    """Every candidate chunk for this query: (payload, vector). Filtered by project_id
    (mandatory for project search, §12.3) and/or document_type (§9.1 `document_types` /
    §9.2 `category` — both reuse the same payload field, see DAY6_UNDERSTANDING.md).
    """
    must = []
    if project_id is not None:
        must.append(FieldCondition(key="project_id", match=MatchValue(value=project_id)))
    if document_types:
        must.append(FieldCondition(key="document_type", match=MatchAny(any=document_types)))
    query_filter = Filter(must=must) if must else None

    points, _ = client.scroll(
        collection_name=collection,
        scroll_filter=query_filter,
        with_payload=True,
        with_vectors=True,
        limit=_SCROLL_LIMIT,
    )
    return [(point.payload, point.vector) for point in points]


def _dense_scores(query_vector: list[float], corpus: list[tuple[dict, list[float]]]) -> dict[str, float]:
    """Cosine similarity via dot product — every embedding is already normalized (Day 5)."""
    return {
        payload["chunk_id"]: sum(q * v for q, v in zip(query_vector, vector, strict=True))
        for payload, vector in corpus
    }


def _bm25_scores(query: str, corpus: list[tuple[dict, list[float]]]) -> dict[str, float]:
    if not corpus:
        return {}
    tokenized_corpus = [_tokenize(payload["text"]) for payload, _ in corpus]
    bm25 = BM25Okapi(tokenized_corpus)
    scores = bm25.get_scores(_tokenize(query))
    return {payload["chunk_id"]: score for (payload, _), score in zip(corpus, scores, strict=True)}


def _rrf_fuse(rank_lists: list[list[str]], k: int = RRF_K) -> dict[str, float]:
    """`score = sum(1 / (k + rank))` over each ranking (1-indexed) a chunk_id appears in."""
    fused: dict[str, float] = {}
    for ranking in rank_lists:
        for rank, chunk_id in enumerate(ranking, start=1):
            fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return fused


def hybrid_search(
    client: QdrantClient,
    collection: str,
    embedder: EmbeddingService,
    query: str,
    top_k: int = 5,
    project_id: str | None = None,
    document_types: list[str] | None = None,
) -> list[RetrievedChunk]:
    corpus = _scroll_corpus(client, collection, project_id, document_types)
    if not corpus:
        return []

    query_vector = embedder.embed_query(query)
    dense_scores = _dense_scores(query_vector, corpus)
    bm25_scores = _bm25_scores(query, corpus)

    dense_rank = sorted(dense_scores, key=lambda cid: dense_scores[cid], reverse=True)
    bm25_rank = sorted(bm25_scores, key=lambda cid: bm25_scores[cid], reverse=True)
    fused = _rrf_fuse([dense_rank, bm25_rank])
    top_ids = sorted(fused, key=lambda cid: fused[cid], reverse=True)[:top_k]

    payload_by_id = {payload["chunk_id"]: payload for payload, _ in corpus}
    return [
        RetrievedChunk(**payload_by_id[chunk_id], similarity_score=dense_scores[chunk_id])
        for chunk_id in top_ids
    ]

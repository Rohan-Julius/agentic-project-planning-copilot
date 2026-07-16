"""Vector storage (Day 5, DESIGN.md §5.4) — deterministic Qdrant I/O, no LLM reasoning.

Two collections (§12.1), both dim 384/cosine: `project_knowledge` (per-project) and
`organizational_knowledge` (shared standards). Project isolation is a **physical
collection split plus a mandatory project_id filter on project reads** (§12.3) — not just
a payload filter that a caller could forget to apply.
"""
from __future__ import annotations

import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    ScoredPoint,
    VectorParams,
)

from app.config import get_settings
from app.schemas.document import ChunkPayload

_VECTOR_SIZE = 384


def _point_id(chunk_id: str) -> str:
    """Qdrant point IDs must be an unsigned int or UUID; chunk_id (§0.2 ID scheme) is
    neither, so map it to a stable UUID — re-upserting the same chunk_id updates the same
    point rather than creating a duplicate.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


class VectorService:
    def __init__(self, client: QdrantClient | None = None) -> None:
        settings = get_settings()
        self.client = client or QdrantClient(url=settings.qdrant_url)
        for collection in (settings.qdrant_project_collection, settings.qdrant_org_collection):
            self._ensure_collection(collection)

    def _ensure_collection(self, collection: str) -> None:
        if not self.client.collection_exists(collection):
            self.client.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE),
            )

    def upsert_chunks(
        self, collection: str, chunks: list[ChunkPayload], vectors: list[list[float]]
    ) -> None:
        points = [
            PointStruct(id=_point_id(chunk.chunk_id), vector=vector, payload=chunk.model_dump())
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        if points:
            self.client.upsert(collection_name=collection, points=points)

    def delete_by_document(self, collection: str, document_id: str) -> None:
        self.client.delete(
            collection_name=collection,
            points_selector=Filter(
                must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
            ),
        )

    def search(
        self,
        collection: str,
        query_vector: list[float],
        query_filter: Filter | None,
        top_k: int,
    ) -> list[ScoredPoint]:
        return self.client.query_points(
            collection_name=collection,
            query=query_vector,
            query_filter=query_filter,
            limit=top_k,
        ).points

    def search_project(
        self, collection: str, project_id: str, query_vector: list[float], top_k: int
    ) -> list[ScoredPoint]:
        """§12.3: every project-document query must filter by project_id."""
        query_filter = Filter(
            must=[FieldCondition(key="project_id", match=MatchValue(value=project_id))]
        )
        return self.search(collection, query_vector, query_filter, top_k)

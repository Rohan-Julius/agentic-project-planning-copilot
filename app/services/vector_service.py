"""Vector storage (Day 5, DESIGN.md §5.4) — deterministic Qdrant I/O, no LLM reasoning.

Two collections (§12.1), both dim 384/cosine: `project_knowledge` (per-project) and
`organizational_knowledge` (shared standards). Project isolation is a **physical
collection split plus a mandatory project_id filter on project reads** (§12.3) — not just
a payload filter that a caller could forget to apply.
"""
from __future__ import annotations

import uuid
from functools import lru_cache

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


class VectorServiceUnavailableError(RuntimeError):
    """Raised when the configured Qdrant backend cannot be reached or initialized (spec
    §25 "Chroma/Qdrant unavailable" negative case). Callers must never let the underlying
    qdrant-client/httpx exception propagate raw past this point — app/main.py registers an
    exception handler that maps this one type to a clean 503 with a stable `{"detail": ...}`
    body, matching every other error response in this app (see frontend/src/api/client.ts's
    ApiError). Letting the raw exception escape instead produces an unhandled Starlette 500
    that skips CORSMiddleware's normal response path, which the browser reports as a bare
    "Failed to fetch" with no usable detail (diagnosed docs/PROJECT_PLAN.md Day 14).
    """


class VectorService:
    def __init__(self, client: QdrantClient | None = None) -> None:
        settings = get_settings()
        try:
            if client is not None:
                self.client = client
            elif settings.qdrant_url:
                self.client = QdrantClient(url=settings.qdrant_url)
            else:
                self.client = QdrantClient(path=str(settings.qdrant_local_path))
            for collection in (
                settings.qdrant_project_collection,
                settings.qdrant_org_collection,
            ):
                self._ensure_collection(collection)
        except VectorServiceUnavailableError:
            raise
        except Exception as exc:
            raise VectorServiceUnavailableError(
                f"Qdrant vector store is not reachable: {exc}"
            ) from exc

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

    def list_by_document(
        self, collection: str, project_id: str, document_id: str
    ) -> list[ChunkPayload]:
        """Every chunk currently stored for one document (§16.3 "viewing chunks"), project-
        filtered (§12.3) same as every other project read. Returns `[]` for a document that
        hasn't been indexed yet rather than raising — that's a legitimate state, not an
        error. A plain `scroll` (not `search`) since this has no query vector — it's a
        lookup by payload fields, not a similarity search. `limit` is generous rather than
        paginated: chunking (§5) caps how large any one section can be before it splits, so
        a single document's chunk count stays small enough that one page is always enough
        for this PoC's scale.
        """
        query_filter = Filter(
            must=[
                FieldCondition(key="document_id", match=MatchValue(value=document_id)),
                FieldCondition(key="project_id", match=MatchValue(value=project_id)),
            ]
        )
        points, _ = self.client.scroll(
            collection_name=collection,
            scroll_filter=query_filter,
            limit=10_000,
            with_payload=True,
            with_vectors=False,
        )
        # scroll() makes no ordering guarantee (it walks internal storage segments, not
        # insertion order) — sort by chunk_id, which is the document's own reading-order
        # sequence (chunking_service assigns "{document_id}-CH-{index:03d}" in order), so
        # callers see chunks in the order they actually appear in the source document.
        chunks = [ChunkPayload.model_validate(point.payload) for point in points]
        return sorted(chunks, key=lambda chunk: chunk.chunk_id)


@lru_cache
def get_vector_service() -> VectorService:
    """Process-wide singleton (FastAPI-dependency-overridable in tests, same pattern as
    `get_settings`/`get_engine`).
    """
    return VectorService()

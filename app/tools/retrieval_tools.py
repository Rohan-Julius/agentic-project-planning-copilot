"""Retrieval tools (spec §9.1, §9.2, §9.10) — the agent<->retrieval boundary.

Every project search is filtered by `project_id` in the signature itself (§12.3/§20.4) —
there is no code path that queries `project_knowledge` without one. `search_company_standards`
queries `organizational_knowledge` only and never accepts a `project_id`.

Tools run outside the FastAPI request cycle (agents/workflow nodes call them directly from
Day 7 onward), so the optional `vector_service`/`embedder` keyword-only params exist purely for
test injection, defaulting to the process-wide cached singletons — see DAY6_UNDERSTANDING.md
decision 5. The required, spec-fixed args are all positional/keyword-with-default, unaffected.
"""
from __future__ import annotations

from app.config import get_settings
from app.schemas.document import RetrievedChunk
from app.services.embedding_service import EmbeddingService, get_embedding_service
from app.services.retrieval_service import hybrid_search
from app.services.vector_service import VectorService, get_vector_service


def search_project_documents(
    project_id: str,
    query: str,
    document_types: list[str] | None = None,
    top_k: int = 5,
    *,
    vector_service: VectorService | None = None,
    embedder: EmbeddingService | None = None,
) -> list[RetrievedChunk]:
    """§9.1 — ALWAYS filters by project_id."""
    vector_service = vector_service or get_vector_service()
    embedder = embedder or get_embedding_service()
    return hybrid_search(
        vector_service.client,
        get_settings().qdrant_project_collection,
        embedder,
        query,
        top_k,
        project_id=project_id,
        document_types=document_types,
    )


def search_company_standards(
    query: str,
    category: str | None = None,
    top_k: int = 5,
    *,
    vector_service: VectorService | None = None,
    embedder: EmbeddingService | None = None,
) -> list[RetrievedChunk]:
    """§9.2 — queries `organizational_knowledge` only. `category` reuses the `document_type`
    payload field (see DAY6_UNDERSTANDING.md decision 4).
    """
    vector_service = vector_service or get_vector_service()
    embedder = embedder or get_embedding_service()
    return hybrid_search(
        vector_service.client,
        get_settings().qdrant_org_collection,
        embedder,
        query,
        top_k,
        project_id=None,
        document_types=[category] if category else None,
    )


def find_supporting_evidence(
    project_id: str,
    claim: str,
    top_k: int = 5,
    *,
    vector_service: VectorService | None = None,
    embedder: EmbeddingService | None = None,
) -> list[RetrievedChunk]:
    """§9.10 — the Reviewer Agent's grounding lookup; project-filtered like §9.1."""
    return search_project_documents(
        project_id, claim, top_k=top_k, vector_service=vector_service, embedder=embedder
    )

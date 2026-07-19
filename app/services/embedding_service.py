"""Embedding generation (Day 5, DESIGN.md §5.3) — deterministic wrapper, no LLM reasoning.

Loads the Sentence-Transformers model once per `model_name` (module-level cache) so
repeated `EmbeddingService()` construction never re-downloads or re-loads weights.
"""
from __future__ import annotations

from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.config import get_settings


@lru_cache
def _load_model(model_name: str) -> SentenceTransformer:
    return SentenceTransformer(model_name)


class EmbeddingService:
    """Wraps the local bge-small model (§15) — 384-dim, cosine-normalized vectors."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or get_settings().embedding_model
        self._model = _load_model(self.model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return vectors.tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text])[0]

    def count_tokens(self, text: str) -> int:
        return len(self._model.tokenizer.encode(text, add_special_tokens=False))


@lru_cache
def get_embedding_service() -> EmbeddingService:
    """Process-wide singleton (FastAPI-dependency-overridable, same pattern as `get_settings`)."""
    return EmbeddingService()

"""EmbeddingService tests (Day 5, DESIGN.md §5.3) — real model, no mocks."""
from __future__ import annotations

import math

from app.services.embedding_service import EmbeddingService


def _norm(vector: list[float]) -> float:
    return math.sqrt(sum(x * x for x in vector))


def test_embed_returns_one_normalized_384_dim_vector_per_text():
    service = EmbeddingService()

    vectors = service.embed(["hello world", "a second sentence"])

    assert len(vectors) == 2
    for vector in vectors:
        assert len(vector) == 384
        assert math.isclose(_norm(vector), 1.0, abs_tol=1e-3)


def test_embed_query_returns_single_normalized_384_dim_vector():
    service = EmbeddingService()

    vector = service.embed_query("what is the payment flow?")

    assert len(vector) == 384
    assert math.isclose(_norm(vector), 1.0, abs_tol=1e-3)


def test_count_tokens_uses_model_tokenizer_not_char_length():
    service = EmbeddingService()
    text = "This is a short sentence to count tokens for."

    count = service.count_tokens(text)

    # The model's WordPiece tokenizer produces fewer tokens than characters
    # for ordinary English text, and non-zero for non-empty text.
    assert 0 < count < len(text)


def test_same_model_name_shares_underlying_model_instance():
    first = EmbeddingService()
    second = EmbeddingService()

    assert first._model is second._model


def test_default_device_is_cpu_not_gpu_auto_detected():
    """Day 25: defaults to "cpu", not sentence-transformers' own GPU auto-detection (mps on
    Apple Silicon) — live-observed GPU contention with Ollama's own loaded LLM on the same
    machine, up to and including an outright HTTP 500 from Ollama's /api/generate. See
    Settings.embedding_device's docstring in app/config.py.
    """
    service = EmbeddingService()

    assert service.device == "cpu"


def test_explicit_device_override_respected():
    service = EmbeddingService(device="cpu")

    assert service.device == "cpu"


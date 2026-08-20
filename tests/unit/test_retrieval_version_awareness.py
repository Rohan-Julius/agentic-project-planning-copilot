"""Regression tests (Day 23, spec §12.2/Day 21 finding): retrieval must only search the
latest version of a same-named document, never a mix of superseded and current chunks.
"""
from __future__ import annotations

from app.services.retrieval_service import _keep_latest_version_per_document_name


def _chunk(document_name: str, document_version: str, chunk_id: str) -> tuple[dict, list[float]]:
    return ({"document_name": document_name, "document_version": document_version, "chunk_id": chunk_id}, [0.0])


def test_keeps_only_the_latest_version_of_a_repeated_document_name():
    corpus = [
        _chunk("requirements.md", "1.0", "CH-1"),
        _chunk("requirements.md", "2.0", "CH-2"),
        _chunk("requirements.md", "1.0", "CH-3"),
    ]

    result = _keep_latest_version_per_document_name(corpus)

    chunk_ids = {payload["chunk_id"] for payload, _ in result}
    assert chunk_ids == {"CH-2"}


def test_leaves_unrelated_document_names_untouched():
    corpus = [
        _chunk("requirements.md", "2.0", "CH-1"),
        _chunk("other.md", "1.0", "CH-2"),
    ]

    result = _keep_latest_version_per_document_name(corpus)

    chunk_ids = {payload["chunk_id"] for payload, _ in result}
    assert chunk_ids == {"CH-1", "CH-2"}


def test_handles_a_missing_or_malformed_version_gracefully():
    corpus = [
        ({"document_name": "x.md", "chunk_id": "CH-1"}, [0.0]),  # no document_version key
        _chunk("x.md", "2.0", "CH-2"),
    ]

    result = _keep_latest_version_per_document_name(corpus)

    chunk_ids = {payload["chunk_id"] for payload, _ in result}
    assert chunk_ids == {"CH-2"}

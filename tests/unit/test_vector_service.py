"""Vector storage tests (Day 5, DESIGN.md §5.4) — real qdrant-client, in-memory backend,
no mocks. project_knowledge / organizational_knowledge are separate collections (§12.1);
project isolation is a physical collection split, not just a payload filter.
"""
from __future__ import annotations

import pytest
from qdrant_client import QdrantClient

from app.schemas.document import ChunkPayload
from app.services.vector_service import VectorService, VectorServiceUnavailableError


def _service() -> VectorService:
    return VectorService(client=QdrantClient(location=":memory:"))


def _chunk(chunk_id, project_id, text="some chunk text", document_id="doc_1") -> ChunkPayload:
    return ChunkPayload(
        chunk_id=chunk_id,
        project_id=project_id,
        document_id=document_id,
        document_name="requirements.pdf",
        document_type="business_requirement",
        source_type="project",
        document_version="1.0",
        text=text,
        page_number=1,
        section="Payment Processing",
        section_hierarchy_path="3. Functional > 3.2 Payment Processing",
    )


def _vector(seed: float) -> list[float]:
    vector = [0.0] * 384
    vector[0] = seed
    vector[1] = 1.0
    return vector


def test_upsert_then_search_returns_the_chunk_with_full_metadata():
    service = _service()
    chunk = _chunk("doc_1-CH-001", project_id="proj_a")

    service.upsert_chunks("project_knowledge", [chunk], [_vector(1.0)])
    results = service.search("project_knowledge", _vector(1.0), query_filter=None, top_k=5)

    assert len(results) == 1
    payload = results[0].payload
    assert payload["chunk_id"] == "doc_1-CH-001"
    assert payload["project_id"] == "proj_a"
    assert payload["section"] == "Payment Processing"
    assert payload["page_number"] == 1


def test_search_project_filter_never_returns_another_projects_chunks():
    """Checkpoint 1 (DESIGN.md §5.4): project isolation."""
    service = _service()
    chunk_a = _chunk("doc_1-CH-001", project_id="proj_a", document_id="doc_1")
    chunk_b = _chunk("doc_2-CH-001", project_id="proj_b", document_id="doc_2")
    service.upsert_chunks(
        "project_knowledge", [chunk_a, chunk_b], [_vector(1.0), _vector(1.0)]
    )

    results = service.search_project(
        "project_knowledge", project_id="proj_a", query_vector=_vector(1.0), top_k=10
    )

    assert len(results) == 1
    assert results[0].payload["project_id"] == "proj_a"


def test_delete_by_document_stops_further_retrieval():
    service = _service()
    chunk = _chunk("doc_1-CH-001", project_id="proj_a", document_id="doc_1")
    service.upsert_chunks("project_knowledge", [chunk], [_vector(1.0)])

    service.delete_by_document("project_knowledge", document_id="doc_1")
    results = service.search("project_knowledge", _vector(1.0), query_filter=None, top_k=5)

    assert results == []


def test_list_by_document_returns_every_chunk_for_that_document_with_text():
    service = _service()
    chunk_1 = _chunk("doc_1-CH-001", project_id="proj_a", document_id="doc_1", text="First chunk.")
    chunk_2 = _chunk("doc_1-CH-002", project_id="proj_a", document_id="doc_1", text="Second chunk.")
    service.upsert_chunks(
        "project_knowledge", [chunk_1, chunk_2], [_vector(1.0), _vector(2.0)]
    )

    results = service.list_by_document("project_knowledge", project_id="proj_a", document_id="doc_1")

    assert {r.chunk_id for r in results} == {"doc_1-CH-001", "doc_1-CH-002"}
    assert {r.text for r in results} == {"First chunk.", "Second chunk."}


def test_list_by_document_excludes_other_documents_and_projects():
    service = _service()
    target = _chunk("doc_1-CH-001", project_id="proj_a", document_id="doc_1")
    other_doc = _chunk("doc_2-CH-001", project_id="proj_a", document_id="doc_2")
    other_project = _chunk("doc_1-CH-001b", project_id="proj_b", document_id="doc_1")
    service.upsert_chunks(
        "project_knowledge",
        [target, other_doc, other_project],
        [_vector(1.0), _vector(2.0), _vector(3.0)],
    )

    results = service.list_by_document("project_knowledge", project_id="proj_a", document_id="doc_1")

    assert len(results) == 1
    assert results[0].chunk_id == "doc_1-CH-001"


def test_list_by_document_returns_chunks_in_chunk_id_order():
    """Qdrant's scroll() makes no ordering guarantee — chunks must come back in document
    sequence (chunk_id order), not whatever internal storage order Qdrant happens to use.
    Upserted deliberately out of order to catch a naive "just return what scroll gives me".
    """
    service = _service()
    chunk_3 = _chunk("doc_1-CH-003", project_id="proj_a", document_id="doc_1", text="third")
    chunk_1 = _chunk("doc_1-CH-001", project_id="proj_a", document_id="doc_1", text="first")
    chunk_2 = _chunk("doc_1-CH-002", project_id="proj_a", document_id="doc_1", text="second")
    service.upsert_chunks(
        "project_knowledge",
        [chunk_3, chunk_1, chunk_2],
        [_vector(3.0), _vector(1.0), _vector(2.0)],
    )

    results = service.list_by_document("project_knowledge", project_id="proj_a", document_id="doc_1")

    assert [r.chunk_id for r in results] == ["doc_1-CH-001", "doc_1-CH-002", "doc_1-CH-003"]


def test_list_by_document_returns_empty_list_when_never_indexed():
    service = _service()

    results = service.list_by_document("project_knowledge", project_id="proj_a", document_id="doc_1")

    assert results == []


def test_project_and_organizational_collections_are_physically_separate():
    service = _service()
    project_chunk = _chunk("doc_1-CH-001", project_id="proj_a", document_id="doc_1")
    org_chunk = _chunk(
        "org_doc_1-CH-001", project_id="", document_id="org_doc_1", text="Definition of Done"
    )

    service.upsert_chunks("project_knowledge", [project_chunk], [_vector(1.0)])
    service.upsert_chunks("organizational_knowledge", [org_chunk], [_vector(1.0)])

    org_results = service.search(
        "organizational_knowledge", _vector(1.0), query_filter=None, top_k=10
    )

    assert len(org_results) == 1
    assert org_results[0].payload["chunk_id"] == "org_doc_1-CH-001"


def test_upsert_is_idempotent_for_the_same_chunk_id():
    service = _service()
    chunk = _chunk("doc_1-CH-001", project_id="proj_a")

    service.upsert_chunks("project_knowledge", [chunk], [_vector(1.0)])
    service.upsert_chunks("project_knowledge", [chunk], [_vector(1.0)])
    results = service.search("project_knowledge", _vector(1.0), query_filter=None, top_k=10)

    assert len(results) == 1


def test_falls_back_to_embedded_local_qdrant_when_url_is_unset(tmp_path, monkeypatch):
    from app.config import Settings, get_settings

    local_settings = Settings(_env_file=None, DATA_DIR=str(tmp_path))
    assert local_settings.qdrant_url is None
    get_settings.cache_clear()
    monkeypatch.setattr("app.services.vector_service.get_settings", lambda: local_settings)

    service = VectorService()
    chunk = _chunk("doc_1-CH-001", project_id="proj_a")
    service.upsert_chunks("project_knowledge", [chunk], [_vector(1.0)])
    results = service.search("project_knowledge", _vector(1.0), query_filter=None, top_k=5)

    assert len(results) == 1
    assert results[0].payload["chunk_id"] == "doc_1-CH-001"
    assert (tmp_path / "qdrant_local").exists()

    get_settings.cache_clear()


def test_vector_service_raises_clean_error_when_qdrant_connection_fails():
    """§25 'Chroma/Qdrant unavailable': a broken client (connection refused, wrong host,
    server down) must surface as VectorServiceUnavailableError, never a raw qdrant-client/
    httpx exception — app/main.py's exception handler only knows how to translate this one
    type into a clean 503.
    """

    class _RaisingClient:
        def collection_exists(self, name):
            raise ConnectionError("Connection refused")

    with pytest.raises(VectorServiceUnavailableError) as exc_info:
        VectorService(client=_RaisingClient())

    assert "Qdrant vector store is not reachable" in str(exc_info.value)
    # The original exception must still be reachable for logging/debugging.
    assert isinstance(exc_info.value.__cause__, ConnectionError)

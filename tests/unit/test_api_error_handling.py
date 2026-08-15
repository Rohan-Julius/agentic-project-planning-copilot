"""API-layer negative tests (spec §25 'Chroma/Qdrant unavailable' + general unhandled-error
hardening) — proves a broken vector-store dependency (or any other unexpected exception)
degrades to a clean, CORS-safe JSON error instead of an unhandled 500 that skips
CORSMiddleware's normal response path (diagnosed docs/PROJECT_PLAN.md Day 14 — the browser
reports these as a bare "Failed to fetch" with no usable detail).
"""
from __future__ import annotations

from app.services.vector_service import VectorServiceUnavailableError, get_vector_service


def _create_project(client) -> str:
    response = client.post("/projects", json={"name": "Error Handling Test"})
    return response.json()["project_id"]


def test_vector_service_unavailable_returns_clean_503_with_cors_header(client):
    """Simulates Qdrant being down for one request by making the dependency itself raise
    VectorServiceUnavailableError — exactly what get_vector_service() now does for a real
    unreachable Qdrant. Any endpoint depending on it works; /workflow/start is
    representative (it depends on vector_service before its own handler logic runs).
    """
    project_id = _create_project(client)

    def _raise_unavailable():
        raise VectorServiceUnavailableError("Qdrant vector store is not reachable: simulated")

    client.app.dependency_overrides[get_vector_service] = _raise_unavailable
    try:
        response = client.post(
            f"/projects/{project_id}/workflow/start",
            headers={"origin": "http://localhost:5173"},
        )
    finally:
        # Restore the working test vector service the `client` fixture originally installed.
        client.app.dependency_overrides[get_vector_service] = lambda: client.vector_service

    assert response.status_code == 503
    assert "not reachable" in response.json()["detail"]
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_unexpected_exception_returns_clean_500_with_cors_header(client):
    """Defense-in-depth: any *other* unhandled exception (not just Qdrant-down) must still
    degrade to a clean, CORS-safe 500 rather than an unhandled crash — proven the same way,
    with a dependency that raises something the app has no specific handler for.
    """
    project_id = _create_project(client)

    def _raise_unexpected():
        raise RuntimeError("simulated unexpected failure")

    client.app.dependency_overrides[get_vector_service] = _raise_unexpected
    try:
        response = client.post(
            f"/projects/{project_id}/workflow/start",
            headers={"origin": "http://localhost:5173"},
        )
    finally:
        client.app.dependency_overrides[get_vector_service] = lambda: client.vector_service

    assert response.status_code == 500
    assert response.json()["detail"]
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"

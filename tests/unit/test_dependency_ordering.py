"""Regression tests (Day 23, Day 17 finding): a nonexistent project must 404 even when Qdrant
is also unavailable — previously the vector_service dependency resolved first and produced a
503 that masked the real problem (the project simply doesn't exist).
"""
from __future__ import annotations

from app.services.vector_service import VectorServiceUnavailableError, get_vector_service


def _raise_unavailable():
    raise VectorServiceUnavailableError("Qdrant unreachable")


def test_start_workflow_404s_for_unknown_project_even_when_qdrant_is_down(client):
    client.app.dependency_overrides[get_vector_service] = _raise_unavailable
    try:
        response = client.post("/projects/proj_does_not_exist/workflow/start")
    finally:
        client.app.dependency_overrides[get_vector_service] = lambda: client.vector_service

    assert response.status_code == 404


def test_workflow_status_404s_for_unknown_project_even_when_qdrant_is_down(client):
    client.app.dependency_overrides[get_vector_service] = _raise_unavailable
    try:
        response = client.get("/projects/proj_does_not_exist/workflow/status")
    finally:
        client.app.dependency_overrides[get_vector_service] = lambda: client.vector_service

    assert response.status_code == 404


def test_approve_clarifications_404s_for_unknown_project_even_when_qdrant_is_down(client):
    client.app.dependency_overrides[get_vector_service] = _raise_unavailable
    try:
        response = client.post("/projects/proj_does_not_exist/clarifications/approve")
    finally:
        client.app.dependency_overrides[get_vector_service] = lambda: client.vector_service

    assert response.status_code == 404


def test_approve_plan_404s_for_unknown_project_even_when_qdrant_is_down(client):
    client.app.dependency_overrides[get_vector_service] = _raise_unavailable
    try:
        response = client.post("/projects/proj_does_not_exist/plan/approve")
    finally:
        client.app.dependency_overrides[get_vector_service] = lambda: client.vector_service

    assert response.status_code == 404


def test_start_workflow_still_503s_for_a_real_project_when_qdrant_is_down(client):
    """Confirms the fix only changes behavior for a nonexistent project — a real project with
    Qdrant down must still surface the genuine 503 (matches Day 17's existing
    test_api_error_handling.py coverage for this endpoint, kept here as a same-file sibling
    proof that the ordering fix didn't regress the original guarantee).
    """
    create_resp = client.post("/projects", json={"name": "Ordering Test"})
    project_id = create_resp.json()["project_id"]

    client.app.dependency_overrides[get_vector_service] = _raise_unavailable
    try:
        response = client.post(f"/projects/{project_id}/workflow/start")
    finally:
        client.app.dependency_overrides[get_vector_service] = lambda: client.vector_service

    assert response.status_code == 503

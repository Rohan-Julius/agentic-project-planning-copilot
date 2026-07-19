"""Index -> search -> delete -> search-returns-nothing, end-to-end through the API
(Day 6, spec §18, §20.4) — for both project and organizational documents.
"""
from __future__ import annotations

from app.tools.retrieval_tools import search_company_standards, search_project_documents


def _create_project(client) -> str:
    response = client.post("/projects", json={"name": "Leave Management"})
    return response.json()["project_id"]


def test_project_document_index_then_delete_cascade(client):
    project_id = _create_project(client)
    upload = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("requirements.txt", b"Payment must support 3D-secure verification.", "text/plain")},
    )
    document_id = upload.json()["document_id"]

    index_response = client.post(f"/projects/{project_id}/index")
    assert index_response.status_code == 200
    body = index_response.json()
    assert document_id in body["indexed_document_ids"]
    assert body["chunk_count"] >= 1

    results = search_project_documents(
        project_id, "3D-secure verification", vector_service=client.vector_service
    )
    assert results and all(r.project_id == project_id for r in results)

    delete_response = client.delete(f"/projects/{project_id}/documents/{document_id}")
    assert delete_response.status_code == 204

    results_after_delete = search_project_documents(
        project_id, "3D-secure verification", vector_service=client.vector_service
    )
    assert results_after_delete == []


def test_organizational_document_index_then_delete_cascade(client):
    upload = client.post(
        "/organizational-documents",
        files={"file": ("dod.txt", b"Definition of Done requires a passing test suite.", "text/plain")},
        data={"document_type": "Definition of Done"},
    )
    assert upload.status_code == 201
    document_id = upload.json()["document_id"]
    assert upload.json()["project_id"] is None

    index_response = client.post("/organizational-documents/index")
    assert index_response.status_code == 200
    assert document_id in index_response.json()["indexed_document_ids"]

    results = search_company_standards(
        "definition of done", vector_service=client.vector_service
    )
    assert results and all(r.source_type == "organizational" for r in results)

    delete_response = client.delete(f"/organizational-documents/{document_id}")
    assert delete_response.status_code == 204

    results_after_delete = search_company_standards(
        "definition of done", vector_service=client.vector_service
    )
    assert results_after_delete == []


def test_reindex_does_not_duplicate_chunks(client):
    project_id = _create_project(client)
    upload = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("requirements.txt", b"Single short requirement statement.", "text/plain")},
    )
    document_id = upload.json()["document_id"]

    first = client.post(f"/projects/{project_id}/index").json()
    second = client.post(f"/projects/{project_id}/index", params={"force": True}).json()

    assert document_id in first["indexed_document_ids"]
    assert document_id in second["indexed_document_ids"]
    assert first["chunk_count"] == second["chunk_count"]

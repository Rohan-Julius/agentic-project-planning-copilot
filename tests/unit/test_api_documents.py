"""Day 3: document upload/storage API tests (spec §18, §16.3)."""
from __future__ import annotations


def _create_project(client) -> str:
    response = client.post("/projects", json={"name": "Leave Management"})
    return response.json()["project_id"]


def test_upload_document(client):
    project_id = _create_project(client)
    response = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("requirements.txt", b"Users can log in.", "text/plain")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["document_name"] == "requirements.txt"
    assert body["document_version"] == "1.0"
    assert body["project_id"] == project_id


def test_upload_duplicate_name_increments_version(client):
    project_id = _create_project(client)
    client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("spec.txt", b"v1", "text/plain")},
    )
    response = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("spec.txt", b"v2", "text/plain")},
    )
    assert response.json()["document_version"] == "2.0"


def test_upload_unsupported_format_rejected(client):
    project_id = _create_project(client)
    response = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("malware.exe", b"binary", "application/octet-stream")},
    )
    assert response.status_code == 422


def test_upload_to_missing_project_returns_404(client):
    response = client.post(
        "/projects/does-not-exist/documents",
        files={"file": ("spec.txt", b"content", "text/plain")},
    )
    assert response.status_code == 404


def test_list_documents(client):
    project_id = _create_project(client)
    client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("a.txt", b"a", "text/plain")},
    )
    client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("b.txt", b"b", "text/plain")},
    )
    response = client.get(f"/projects/{project_id}/documents")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_create_text_document(client):
    project_id = _create_project(client)
    response = client.post(
        f"/projects/{project_id}/documents/text",
        json={"document_name": "notes", "content": "Free-text requirement notes."},
    )
    assert response.status_code == 201
    assert response.json()["document_name"] == "notes.txt"


def test_delete_document(client):
    project_id = _create_project(client)
    upload = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("a.txt", b"a", "text/plain")},
    )
    document_id = upload.json()["document_id"]
    response = client.delete(f"/projects/{project_id}/documents/{document_id}")
    assert response.status_code == 204
    assert client.get(f"/projects/{project_id}/documents").json() == []

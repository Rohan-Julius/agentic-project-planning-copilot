"""Day 3: document upload/storage API tests (spec §18, §16.3)."""
from __future__ import annotations


def _create_project(client, name: str = "Leave Management") -> str:
    response = client.post("/projects", json={"name": name})
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


def test_upload_document_captures_document_type_from_form_data(client):
    """Regression test (Day 21): document_type must be declared with `= Form(...)`, not a
    plain default, alongside an UploadFile parameter — otherwise FastAPI never reads it from
    the multipart body and it silently stays empty regardless of what's sent, breaking §9.1's
    document_types filter for every uploaded document. Found live via §24.9's
    metadata-filtered retrieval queries returning zero results for a real, indexed document.
    """
    project_id = _create_project(client)
    response = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("requirements.txt", b"Users can log in.", "text/plain")},
        data={"document_type": "business_requirement"},
    )
    assert response.status_code == 201
    assert response.json()["document_type"] == "business_requirement"


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


def test_get_document_text_returns_extracted_blocks(client):
    """§16.3 "viewing extracted text" — re-parsed on demand from the stored file."""
    project_id = _create_project(client)
    upload = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("notes.txt", b"Users can log in with email and password.", "text/plain")},
    )
    document_id = upload.json()["document_id"]

    response = client.get(f"/projects/{project_id}/documents/{document_id}/text")

    assert response.status_code == 200
    body = response.json()
    assert body["document_id"] == document_id
    assert len(body["blocks"]) == 1
    assert body["blocks"][0]["text"] == "Users can log in with email and password."


def test_get_document_text_returns_404_for_unknown_document(client):
    project_id = _create_project(client)
    response = client.get(f"/projects/{project_id}/documents/does-not-exist/text")
    assert response.status_code == 404


def test_get_document_text_returns_404_for_unknown_project(client):
    response = client.get("/projects/does-not-exist/documents/doc_1/text")
    assert response.status_code == 404


def test_get_document_text_is_project_isolated(client):
    """A document_id that's real, but belongs to a different project, must 404 — not leak
    across projects (§12.3, §20.4).
    """
    project_a = _create_project(client, name="Project A")
    project_b = _create_project(client, name="Project B")
    upload = client.post(
        f"/projects/{project_a}/documents",
        files={"file": ("a.txt", b"secret", "text/plain")},
    )
    document_id = upload.json()["document_id"]

    response = client.get(f"/projects/{project_b}/documents/{document_id}/text")

    assert response.status_code == 404


def test_get_document_chunks_returns_empty_before_indexing(client):
    """§16.3 "viewing chunks" — not-yet-indexed is a legitimate empty state, not an error."""
    project_id = _create_project(client)
    upload = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("a.txt", b"a", "text/plain")},
    )
    document_id = upload.json()["document_id"]

    response = client.get(f"/projects/{project_id}/documents/{document_id}/chunks")

    assert response.status_code == 200
    assert response.json() == []


def test_get_document_chunks_returns_404_for_unknown_document(client):
    project_id = _create_project(client)
    response = client.get(f"/projects/{project_id}/documents/does-not-exist/chunks")
    assert response.status_code == 404

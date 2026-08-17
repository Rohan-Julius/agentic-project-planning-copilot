"""Organizational-document (company standards) endpoint tests (app/api/standards.py)."""
from __future__ import annotations


def test_upload_organizational_document_captures_document_type_from_form_data(client):
    """Regression test (Day 21): same bug as documents.py's upload endpoint — document_type
    must be declared with `= Form(...)`, not a plain default, alongside an UploadFile
    parameter, or FastAPI never reads it from the multipart body. Found live via §24.9's
    metadata-filtered retrieval queries against company standards returning zero results.
    """
    response = client.post(
        "/organizational-documents",
        files={"file": ("dor.md", b"# Definition of Ready", "text/markdown")},
        data={"document_type": "Definition of Ready"},
    )
    assert response.status_code == 201
    assert response.json()["document_type"] == "Definition of Ready"

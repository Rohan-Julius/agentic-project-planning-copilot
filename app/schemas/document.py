"""Document upload/read schemas (spec §16.3, §22).

`document_type` (categorisation) is intentionally free-text, matching the same choice
made for clarification `category` (app/schemas/clarification.py) — the spec does not
fix a taxonomy.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


class DocumentRead(BaseModel):
    document_id: str
    project_id: str
    document_name: str
    document_type: str = ""
    source_type: str = "project"
    document_version: str
    status: str


class DocumentTextCreate(BaseModel):
    """Text-input path from the document workspace (§16.3) — no file upload."""

    document_name: str = Field(min_length=1)
    content: str = Field(min_length=1)
    document_type: str = ""

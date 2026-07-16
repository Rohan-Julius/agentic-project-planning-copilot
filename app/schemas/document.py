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


class ParsedBlock(BaseModel):
    """One normalized unit of extracted text (§DESIGN.md §4) — a PDF text block, a DOCX
    paragraph, or a TXT/Markdown paragraph. The chunker (Day 5) consumes these directly.
    """

    text: str
    page_number: int | None = None
    heading_level: int | None = None  # 1..N; None = body text
    section_hierarchy_path: str = ""  # e.g. "3. Functional Req > 3.2 Reporting"


class ParsedDocument(BaseModel):
    document_id: str
    blocks: list[ParsedBlock]


class ChunkPayload(BaseModel):
    """One chunk ready for embedding + Qdrant upsert (§12.2) — written to the Qdrant
    payload verbatim and mirrored (minus `text`) into `document_chunk_meta`.
    """

    chunk_id: str
    project_id: str
    document_id: str
    document_name: str
    document_type: str = ""
    source_type: str = "project"
    document_version: str
    text: str
    page_number: int | None = None
    section: str = ""
    section_hierarchy_path: str = ""

"""Document + chunk-metadata mirror tables (spec §12.2, §16.3, §22).

DocumentChunkMeta duplicates chunk metadata (never embeddings) from Qdrant so the
Day-13 citation validator can check "does this chunk_id exist" with a fast indexed SQL
query instead of a per-citation Qdrant round-trip — supporting the project's strict
citation/grounding rule (see docs/ARCHITECTURE.md §5a).
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DocumentRecord(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    # NULL for organizational documents (no project scope) — see DAY6_UNDERSTANDING.md.
    project_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("projects.project_id"), index=True, nullable=True
    )
    document_name: Mapped[str] = mapped_column(String)
    document_type: Mapped[str] = mapped_column(String, default="")
    source_type: Mapped[str] = mapped_column(String, default="project")
    file_path: Mapped[str] = mapped_column(String)
    document_version: Mapped[str] = mapped_column(String, default="1.0")
    status: Mapped[str] = mapped_column(String, default="UPLOADED")
    uploaded_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=lambda: dt.datetime.now(dt.timezone.utc)
    )


class DocumentChunkMeta(Base):
    __tablename__ = "document_chunk_meta"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chunk_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    document_id: Mapped[str] = mapped_column(
        String, ForeignKey("documents.document_id"), index=True
    )
    project_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str] = mapped_column(String, default="")
    section_hierarchy_path: Mapped[str] = mapped_column(String, default="")
    document_version: Mapped[str] = mapped_column(String, default="1.0")

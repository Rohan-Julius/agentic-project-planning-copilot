"""document_chunk_meta mirror persistence (Day 5, DESIGN.md §5.2/§12.2)."""
from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models.base import Base
from app.models.document import DocumentChunkMeta
from app.schemas.document import ChunkPayload
from app.services.document_service import save_chunk_meta


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return Session(engine)


def _chunk(chunk_id="doc_1-CH-001") -> ChunkPayload:
    return ChunkPayload(
        chunk_id=chunk_id,
        project_id="proj_a",
        document_id="doc_1",
        document_name="requirements.pdf",
        document_type="business_requirement",
        source_type="project",
        document_version="1.0",
        text="chunk text",
        page_number=5,
        section="Payment Processing",
        section_hierarchy_path="3. Functional > 3.2 Payment Processing",
    )


def test_save_chunk_meta_persists_all_metadata_fields():
    session = _session()

    save_chunk_meta(session, [_chunk()])

    row = session.scalar(select(DocumentChunkMeta).where(DocumentChunkMeta.chunk_id == "doc_1-CH-001"))
    assert row is not None
    assert row.document_id == "doc_1"
    assert row.project_id == "proj_a"
    assert row.page_number == 5
    assert row.section == "Payment Processing"
    assert row.section_hierarchy_path == "3. Functional > 3.2 Payment Processing"
    assert row.document_version == "1.0"


def test_save_chunk_meta_upserts_same_chunk_id_instead_of_duplicating():
    session = _session()
    save_chunk_meta(session, [_chunk()])

    updated = _chunk()
    updated.section = "Refund Processing"
    save_chunk_meta(session, [updated])

    rows = session.scalars(
        select(DocumentChunkMeta).where(DocumentChunkMeta.chunk_id == "doc_1-CH-001")
    ).all()
    assert len(rows) == 1
    assert rows[0].section == "Refund Processing"

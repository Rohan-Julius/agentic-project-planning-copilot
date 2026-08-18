"""Deterministic citation-field correction (Day 22, CLAUDE.md 'strict citation & grounding,
enforced deterministically, not just prompts').

Every SourceReference an agent produces is checked, not trusted: `chunk_id` is the only field
the LLM needs to get right (agents already copy it from a real retrieved chunk in their
prompt context); `document_name`, `page_number`, and `section` are always overwritten from the
authoritative `document_chunk_meta`/`documents` rows for that chunk_id. A `chunk_id` that
doesn't resolve to a real, indexed chunk for this project is left completely untouched — that
failure mode (a dangling citation) is already caught by
`app/tools/validation_tools.py::validate_project_plan`'s MISSING_SOURCE_REFERENCE /
dangling-citation check, which is the single authority for it; this module's job is narrower
(fix real citations, don't paper over fake ones).
"""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.database.session import get_sessionmaker
from app.models.document import DocumentChunkMeta, DocumentRecord
from app.schemas.common import SourceReference

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker


def correct_source_references(
    refs: list[SourceReference],
    project_id: str,
    *,
    session_factory: "Callable[[], Session] | sessionmaker | None" = None,
) -> list[SourceReference]:
    """Overwrite document_name/page_number/section on every ref whose chunk_id resolves to a
    real, indexed chunk for this project. Mirrors validate_project_plan's own
    `DocumentChunkMeta.project_id == project_id` filter (§12.3 project isolation) so this
    function can never "correct" a reference using another project's chunk metadata.
    """
    if not refs:
        return refs

    factory = session_factory or get_sessionmaker()
    session = factory()
    try:
        chunk_ids = [ref.chunk_id for ref in refs]
        rows = session.execute(
            select(
                DocumentChunkMeta.chunk_id,
                DocumentRecord.document_name,
                DocumentChunkMeta.page_number,
                DocumentChunkMeta.section,
            )
            .join(DocumentRecord, DocumentChunkMeta.document_id == DocumentRecord.document_id)
            .where(
                DocumentChunkMeta.project_id == project_id,
                DocumentChunkMeta.chunk_id.in_(chunk_ids),
            )
        ).all()
        by_chunk_id = {
            chunk_id: (document_name, page_number, section)
            for chunk_id, document_name, page_number, section in rows
        }
    finally:
        session.close()

    corrected: list[SourceReference] = []
    for ref in refs:
        match = by_chunk_id.get(ref.chunk_id)
        if match is None:
            corrected.append(ref)
            continue
        document_name, page_number, section = match
        corrected.append(
            ref.model_copy(
                update={
                    "document_name": document_name,
                    "page_number": page_number,
                    "section": section or None,
                }
            )
        )
    return corrected

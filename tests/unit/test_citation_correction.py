"""Regression tests for the Day 22 citation-field correction pass (spec CLAUDE.md 'strict
citation & grounding, enforced deterministically, not just prompts'). The LLM only needs to
get `chunk_id` right; every other field on a SourceReference is corrected from
`document_chunk_meta`/`documents`, never trusted from model output.
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.document import DocumentChunkMeta, DocumentRecord
from app.schemas.common import SourceReference
from app.services.citation_correction import correct_source_references


def _make_session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _seed_chunk(factory, *, project_id="proj_1", chunk_id="DOC-001-CH-003"):
    session = factory()
    session.add(
        DocumentRecord(
            document_id="DOC-001",
            project_id=project_id,
            document_name="requirements.md",
            file_path="/data/requirements.md",
        )
    )
    session.add(
        DocumentChunkMeta(
            chunk_id=chunk_id,
            document_id="DOC-001",
            project_id=project_id,
            page_number=5,
            section="3. Functional Requirements",
        )
    )
    session.commit()
    session.close()


def test_corrects_document_name_page_and_section_for_a_real_chunk():
    factory = _make_session_factory()
    _seed_chunk(factory)
    refs = [
        SourceReference(
            document_name="requirements.pdf",  # wrong — model invented this
            page_number=99,  # wrong
            section="3.6 Reporting",  # wrong — model invented this (the real Day-19 bug)
            chunk_id="DOC-001-CH-003",  # real chunk_id, correctly copied
        )
    ]

    corrected = correct_source_references(refs, "proj_1", session_factory=factory)

    assert corrected[0].document_name == "requirements.md"
    assert corrected[0].page_number == 5
    assert corrected[0].section == "3. Functional Requirements"
    assert corrected[0].chunk_id == "DOC-001-CH-003"


def test_leaves_a_dangling_chunk_id_untouched():
    factory = _make_session_factory()
    _seed_chunk(factory)
    refs = [
        SourceReference(
            document_name="made_up.pdf",
            page_number=1,
            section="invented",
            chunk_id="DOES-NOT-EXIST-CH-001",
        )
    ]

    corrected = correct_source_references(refs, "proj_1", session_factory=factory)

    assert corrected[0].chunk_id == "DOES-NOT-EXIST-CH-001"
    # Untouched — the dangling-citation validator (app/tools/validation_tools.py) is the
    # authority for this failure mode, not this function.
    assert corrected[0].document_name == "made_up.pdf"


def test_does_not_correct_using_another_projects_chunk_metadata():
    """§12.3 project isolation: a chunk_id that exists but belongs to a different project
    must not be used to "correct" this project's citation.
    """
    factory = _make_session_factory()
    _seed_chunk(factory, project_id="proj_OTHER", chunk_id="DOC-001-CH-003")
    refs = [
        SourceReference(
            document_name="made_up.pdf",
            page_number=1,
            section="invented",
            chunk_id="DOC-001-CH-003",
        )
    ]

    corrected = correct_source_references(refs, "proj_1", session_factory=factory)

    assert corrected[0].document_name == "made_up.pdf"


def test_empty_refs_returns_empty_list():
    factory = _make_session_factory()
    assert correct_source_references([], "proj_1", session_factory=factory) == []

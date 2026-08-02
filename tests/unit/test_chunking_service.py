"""Chunking service tests (Day 5, DESIGN.md §5.1) — real tokenizer, no mocks.

Token thresholds are derived from the real EmbeddingService tokenizer at test time
(never hardcoded guesses) so tests stay robust to tokenizer specifics while still
deterministically forcing a specific tier to fire.
"""
from __future__ import annotations

import pytest

from app.models.document import DocumentRecord
from app.schemas.document import ParsedBlock, ParsedDocument
from app.services.chunking_service import chunk_document
from app.services.embedding_service import EmbeddingService


@pytest.fixture(scope="module")
def embedder():
    return EmbeddingService()


def _document(document_id="doc_abc123") -> DocumentRecord:
    return DocumentRecord(
        document_id=document_id,
        project_id="proj_xyz",
        document_name="requirements.pdf",
        document_type="business_requirement",
        source_type="project",
        file_path="/tmp/x",
        document_version="1.0",
    )


def _block(text, page_number=None, heading_level=None, path=""):
    return ParsedBlock(
        text=text,
        page_number=page_number,
        heading_level=heading_level,
        section_hierarchy_path=path,
    )


# --- Tier 1: heading-level sections, each fits under the limit ----------------------


def test_each_level1_section_becomes_its_own_chunk_when_small(embedder):
    blocks = [
        _block("1. Introduction", heading_level=1, path="1. Introduction"),
        _block("Short intro body.", path="1. Introduction"),
        _block("2. Requirements", heading_level=1, path="2. Requirements"),
        _block("Short reqs body.", path="2. Requirements"),
    ]
    parsed = ParsedDocument(document_id="doc_abc123", blocks=blocks)

    chunks = chunk_document(_document(), parsed, embedder, token_limit=200)

    assert len(chunks) == 2
    assert "1. Introduction" in chunks[0].text and "Short intro body." in chunks[0].text
    assert "2. Requirements" in chunks[1].text and "Short reqs body." in chunks[1].text
    assert chunks[0].section_hierarchy_path == "1. Introduction"
    assert chunks[1].section_hierarchy_path == "2. Requirements"


def test_whole_document_is_one_chunk_when_no_headings_and_small(embedder):
    parsed = ParsedDocument(
        document_id="doc_abc123", blocks=[_block("Just one small paragraph of text.")]
    )

    chunks = chunk_document(_document(), parsed, embedder, token_limit=200)

    assert len(chunks) == 1
    assert chunks[0].text == "Just one small paragraph of text."


def test_section_exactly_at_token_limit_does_not_split(embedder):
    """chunk_document's own comparison is `<= limit` throughout (verified in
    app/services/chunking_service.py) — a section whose token count is exactly equal to
    token_limit must stay as one chunk, not split. This locks in the inclusive boundary so a
    future off-by-one change (`<` instead of `<=`) would be caught.
    """
    body = "words words words words words words words words words words"
    blocks = [
        _block("1. Section", heading_level=1, path="1. Section"),
        _block(body, path="1. Section"),
    ]
    parsed = ParsedDocument(document_id="doc_abc123", blocks=blocks)
    exact_tokens = embedder.count_tokens("1. Section " + body)

    chunks = chunk_document(_document(), parsed, embedder, token_limit=exact_tokens)

    assert len(chunks) == 1
    assert "1. Section" in chunks[0].text and body in chunks[0].text


# --- Tier 2: subheading split when a level-1 section is too big ---------------------


def test_oversized_section_splits_by_subheading(embedder):
    sub_a_body = "words words words words words words words words words words"
    sub_b_body = "more more more more more more more more more more more"
    blocks = [
        _block("1. Big Section", heading_level=1, path="1. Big Section"),
        _block("1.1 Sub A", heading_level=2, path="1. Big Section > 1.1 Sub A"),
        _block(sub_a_body, path="1. Big Section > 1.1 Sub A"),
        _block("1.2 Sub B", heading_level=2, path="1. Big Section > 1.2 Sub B"),
        _block(sub_b_body, path="1. Big Section > 1.2 Sub B"),
    ]
    parsed = ParsedDocument(document_id="doc_abc123", blocks=blocks)
    whole_section_tokens = embedder.count_tokens(
        "1. Big Section 1.1 Sub A " + sub_a_body + " 1.2 Sub B " + sub_b_body
    )
    each_subsection_tokens = max(
        embedder.count_tokens("1.1 Sub A " + sub_a_body),
        embedder.count_tokens("1.2 Sub B " + sub_b_body),
    )
    limit = (whole_section_tokens + each_subsection_tokens) // 2
    assert each_subsection_tokens <= limit < whole_section_tokens

    chunks = chunk_document(_document(), parsed, embedder, token_limit=limit)

    assert len(chunks) == 2
    assert chunks[0].section_hierarchy_path == "1. Big Section > 1.1 Sub A"
    assert chunks[1].section_hierarchy_path == "1. Big Section > 1.2 Sub B"


# --- Tier 3: paragraph split when a section has no subheadings ----------------------


def test_oversized_section_with_no_subheadings_splits_by_paragraph(embedder):
    para_a = "alpha alpha alpha alpha alpha alpha alpha alpha alpha alpha"
    para_b = "beta beta beta beta beta beta beta beta beta beta"
    blocks = [
        _block("1. Section", heading_level=1, path="1. Section"),
        _block(para_a, path="1. Section"),
        _block(para_b, path="1. Section"),
    ]
    parsed = ParsedDocument(document_id="doc_abc123", blocks=blocks)
    whole_tokens = embedder.count_tokens("1. Section " + para_a + " " + para_b)
    each_para_tokens = max(embedder.count_tokens(para_a), embedder.count_tokens(para_b))
    limit = (whole_tokens + each_para_tokens) // 2
    assert each_para_tokens <= limit < whole_tokens

    chunks = chunk_document(_document(), parsed, embedder, token_limit=limit)

    assert len(chunks) == 2
    assert para_a in chunks[0].text
    assert para_b in chunks[1].text


# --- Tier 4: sentence packing when a single paragraph is too big --------------------


def test_oversized_paragraph_splits_by_sentence(embedder):
    sentence_a = "Alpha alpha alpha alpha alpha alpha alpha alpha alpha."
    sentence_b = "Beta beta beta beta beta beta beta beta beta."
    blocks = [_block(f"{sentence_a} {sentence_b}")]
    parsed = ParsedDocument(document_id="doc_abc123", blocks=blocks)
    each_sentence_tokens = max(
        embedder.count_tokens(sentence_a), embedder.count_tokens(sentence_b)
    )
    whole_tokens = embedder.count_tokens(f"{sentence_a} {sentence_b}")
    limit = (whole_tokens + each_sentence_tokens) // 2
    assert each_sentence_tokens <= limit < whole_tokens

    chunks = chunk_document(_document(), parsed, embedder, token_limit=limit)

    assert len(chunks) == 2
    assert chunks[0].text.strip() == sentence_a
    assert chunks[1].text.strip() == sentence_b


# --- Tier 5: fixed-size token window with overlap, last resort ----------------------


def test_oversized_single_sentence_falls_back_to_overlapping_fixed_windows(embedder):
    long_blob = " ".join(f"word{i}" for i in range(200)) + "."
    blocks = [_block(long_blob)]
    parsed = ParsedDocument(document_id="doc_abc123", blocks=blocks)

    chunks = chunk_document(
        _document(), parsed, embedder, token_limit=20, overlap_ratio=0.2
    )

    assert len(chunks) > 1
    for chunk in chunks:
        assert embedder.count_tokens(chunk.text) <= 20
    # Consecutive windows overlap: the tail of one appears near the head of the next.
    first_words = chunks[0].text.split()
    second_words = chunks[1].text.split()
    assert set(first_words[-3:]) & set(second_words[:5])


# --- Metadata (§12.2) ----------------------------------------------------------------


def test_chunk_metadata_matches_source_document_and_is_sequential(embedder):
    blocks = [
        _block("1. Introduction", page_number=1, heading_level=1, path="1. Introduction"),
        _block("Body on page one.", page_number=1, path="1. Introduction"),
        _block("2. Requirements", page_number=2, heading_level=1, path="2. Requirements"),
        _block("Body on page two.", page_number=2, path="2. Requirements"),
    ]
    parsed = ParsedDocument(document_id="doc_abc123", blocks=blocks)
    document = _document()

    chunks = chunk_document(document, parsed, embedder, token_limit=200)

    assert [c.chunk_id for c in chunks] == ["doc_abc123-CH-001", "doc_abc123-CH-002"]
    for chunk in chunks:
        assert chunk.project_id == document.project_id
        assert chunk.document_id == document.document_id
        assert chunk.document_name == document.document_name
        assert chunk.document_type == document.document_type
        assert chunk.source_type == document.source_type
        assert chunk.document_version == document.document_version
    assert chunks[0].page_number == 1
    assert chunks[0].section == "1. Introduction"
    assert chunks[1].page_number == 2
    assert chunks[1].section == "2. Requirements"


def test_empty_document_produces_no_chunks(embedder):
    parsed = ParsedDocument(document_id="doc_abc123", blocks=[])

    chunks = chunk_document(_document(), parsed, embedder, token_limit=200)

    assert chunks == []

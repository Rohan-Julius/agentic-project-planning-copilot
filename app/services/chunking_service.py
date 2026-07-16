"""Heading-aware recursive chunking (Day 5, DESIGN.md §5.1) — deterministic, no LLM reasoning.

Ordered fallback: heading (level 1) -> subheading (level 2, 3, ... however deep the
document goes) -> paragraph -> sentence -> fixed-size token window (last resort, overlap
applied only here). Tier 1 always splits by level-1 heading first; every tier below that
only fires when the unit handed to it still exceeds the token limit (DESIGN.md §5.1).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.config import get_settings
from app.models.document import DocumentRecord
from app.schemas.document import ChunkPayload, ParsedBlock, ParsedDocument
from app.services.embedding_service import EmbeddingService

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass
class _Draft:
    text: str
    page_number: int | None
    section: str
    section_hierarchy_path: str


def _group_text(blocks: list[ParsedBlock]) -> str:
    return " ".join(block.text.strip() for block in blocks if block.text.strip())


def _group_to_draft(blocks: list[ParsedBlock]) -> _Draft:
    anchor = blocks[0]
    path_parts = anchor.section_hierarchy_path.split(" > ") if anchor.section_hierarchy_path else []
    page_number = next((b.page_number for b in blocks if b.page_number is not None), None)
    return _Draft(
        text=_group_text(blocks),
        page_number=page_number,
        section=path_parts[-1] if path_parts else "",
        section_hierarchy_path=anchor.section_hierarchy_path,
    )


def _draft_for_text(anchor: _Draft, text: str) -> _Draft:
    return _Draft(
        text=text,
        page_number=anchor.page_number,
        section=anchor.section,
        section_hierarchy_path=anchor.section_hierarchy_path,
    )


def _split_by_heading_level(blocks: list[ParsedBlock], level: int) -> list[list[ParsedBlock]]:
    groups: list[list[ParsedBlock]] = []
    current: list[ParsedBlock] = []
    for block in blocks:
        if block.heading_level == level:
            if current:
                groups.append(current)
            current = [block]
        else:
            current.append(block)
    if current:
        groups.append(current)
    return groups


def _max_heading_level(blocks: list[ParsedBlock]) -> int:
    levels = [b.heading_level for b in blocks if b.heading_level is not None]
    return max(levels) if levels else 0


def _has_body_text(blocks: list[ParsedBlock]) -> bool:
    """A heading with no body under it (e.g. a title immediately followed by a
    subheading) carries no citable content beyond what `section_hierarchy_path`
    metadata already captures on its descendants — such groups are dropped, not chunked.
    """
    return any(b.heading_level is None and b.text.strip() for b in blocks)


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]


def _pack_by_tokens(units: list[str], limit: int, embedder: EmbeddingService) -> list[str]:
    """Greedily pack whole `units` into groups <= limit tokens. A unit that alone exceeds
    `limit` is emitted as its own oversized group for the caller to fall back further on.
    """
    packed: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for unit in units:
        unit_tokens = embedder.count_tokens(unit)
        if current and current_tokens + unit_tokens > limit:
            packed.append(" ".join(current))
            current, current_tokens = [], 0
        current.append(unit)
        current_tokens += unit_tokens
    if current:
        packed.append(" ".join(current))
    return packed


def _fixed_window_split(
    text: str, limit: int, overlap_ratio: float, embedder: EmbeddingService
) -> list[str]:
    """Word-based fixed windows (never raw sub-word token slices): decoding a WordPiece
    token-ID window back to text can start mid-word on a `##`-continuation piece with no
    preceding head token, which re-tokenizes into MORE tokens than the window held. Packing
    whole words by their own token counts keeps every window's real token count <= limit.
    """
    words = text.split()
    if not words:
        return []
    word_tokens = [embedder.count_tokens(word) for word in words]

    windows: list[str] = []
    start = 0
    n = len(words)
    overlap_budget = limit * overlap_ratio
    while start < n:
        end = start
        total = 0
        while end < n and total + word_tokens[end] <= limit:
            total += word_tokens[end]
            end += 1
        end = max(end, start + 1)  # always make progress, even if one word exceeds limit
        windows.append(" ".join(words[start:end]))
        if end >= n:
            break

        back, acc, idx = 0, 0, end - 1
        while idx >= start and acc < overlap_budget:
            acc += word_tokens[idx]
            back += 1
            idx -= 1
        start = max(start + 1, end - back)
    return windows


def _split_paragraph_if_needed(
    draft: _Draft, limit: int, overlap_ratio: float, embedder: EmbeddingService
) -> list[_Draft]:
    if embedder.count_tokens(draft.text) <= limit:
        return [draft]

    # Tier 4: sentence packing.
    sentences = _split_sentences(draft.text) or [draft.text]
    packed = _pack_by_tokens(sentences, limit, embedder)

    results: list[_Draft] = []
    for chunk_text in packed:
        if embedder.count_tokens(chunk_text) <= limit:
            results.append(_draft_for_text(draft, chunk_text))
        else:
            # Tier 5: fixed-size token window (last resort), overlap only here.
            for window_text in _fixed_window_split(chunk_text, limit, overlap_ratio, embedder):
                results.append(_draft_for_text(draft, window_text))
    return results


def _finalize_or_escalate(
    blocks: list[ParsedBlock],
    next_level: int,
    limit: int,
    overlap_ratio: float,
    embedder: EmbeddingService,
) -> list[_Draft]:
    text = _group_text(blocks)
    if embedder.count_tokens(text) <= limit:
        return [_group_to_draft(blocks)] if _has_body_text(blocks) else []

    max_level = _max_heading_level(blocks)
    if next_level <= max_level:
        subgroups = _split_by_heading_level(blocks, next_level)
        if len(subgroups) > 1:
            drafts: list[_Draft] = []
            for subgroup in subgroups:
                drafts.extend(
                    _finalize_or_escalate(subgroup, next_level + 1, limit, overlap_ratio, embedder)
                )
            return drafts
        return _finalize_or_escalate(blocks, next_level + 1, limit, overlap_ratio, embedder)

    # Tier 3: paragraph — one chunk per body block (headings alone aren't chunked; their
    # text is already captured in descendants' section_hierarchy_path), falling further
    # per-block if needed.
    drafts: list[_Draft] = []
    for block in blocks:
        if block.heading_level is not None or not block.text.strip():
            continue
        drafts.extend(
            _split_paragraph_if_needed(_group_to_draft([block]), limit, overlap_ratio, embedder)
        )
    return drafts


def chunk_document(
    document: DocumentRecord,
    parsed: ParsedDocument,
    embedder: EmbeddingService,
    token_limit: int | None = None,
    overlap_ratio: float | None = None,
) -> list[ChunkPayload]:
    """Chunk a parsed document per DESIGN.md §5.1, returning chunks ready for embedding."""
    settings = get_settings()
    limit = token_limit if token_limit is not None else settings.chunk_token_limit
    overlap = overlap_ratio if overlap_ratio is not None else settings.chunk_overlap_ratio

    blocks = [b for b in parsed.blocks if b.text.strip()]
    if not blocks:
        return []

    # Tier 1: always split by level-1 heading first (unconditional baseline granularity).
    top_sections = _split_by_heading_level(blocks, level=1)

    drafts: list[_Draft] = []
    for section in top_sections:
        drafts.extend(_finalize_or_escalate(section, 2, limit, overlap, embedder))

    return [
        ChunkPayload(
            chunk_id=f"{document.document_id}-CH-{index:03d}",
            project_id=document.project_id,
            document_id=document.document_id,
            document_name=document.document_name,
            document_type=document.document_type,
            source_type=document.source_type,
            document_version=document.document_version,
            text=draft.text,
            page_number=draft.page_number,
            section=draft.section,
            section_hierarchy_path=draft.section_hierarchy_path,
        )
        for index, draft in enumerate(drafts, start=1)
    ]


def embedding_text(chunk: ChunkPayload) -> str:
    """Text actually sent to the embedding model (DESIGN.md §5.1) — the stored `text`
    stays clean; only the embedding call sees the hierarchy prefix.
    """
    if not chunk.section_hierarchy_path:
        return chunk.text
    return f"[Section: {chunk.section_hierarchy_path}] {chunk.text}"

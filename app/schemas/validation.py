"""Deterministic-validator result schemas (spec §9.8, §9.9, DESIGN.md §10).

Produced by app/tools/validation_tools.py — pure Python, no LLM. Consumed by the Reviewer
Agent as pre-computed evidence for the checks it doesn't need to judge itself (spec §7.4
checks 2, 3, 6, 9, 11).
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.planning import TraceabilityMatrix


class ValidationIssue(BaseModel):
    """One deterministic-validator finding (spec §9.8)."""

    artifact_id: str
    code: str
    message: str


class ValidationResult(BaseModel):
    """Output of validate_project_plan (spec §9.8)."""

    is_valid: bool
    errors: list[ValidationIssue] = Field(default_factory=list)


class TraceabilityResult(BaseModel):
    """Output of check_traceability (spec §9.9): the traceability matrix plus any gaps in
    the Source Requirement -> Epic -> User Story -> Acceptance Criteria chain.
    """

    matrix: TraceabilityMatrix
    coverage_gaps: list[str] = Field(default_factory=list)
    orphan_story_ids: list[str] = Field(default_factory=list)

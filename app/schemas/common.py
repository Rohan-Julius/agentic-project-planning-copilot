"""Shared building blocks: citations and the grounding invariant (spec §12.4, §12.5, §12.6).

Strict grounding is a project-wide binding rule (see docs/ARCHITECTURE.md §5a): every
SOURCE_BACKED artifact must carry a valid citation. The structural half of that rule (a
citation is present) is enforced right here, at construction time, so invalid agent output
is caught by the retry-once policy (§14) instead of slipping downstream. The referential
half (the citation points at a real, non-deleted chunk) needs a database lookup and is
implemented by the deterministic `validate_project_plan` tool on Day 13.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.schemas.enums import Classification


class SourceReference(BaseModel):
    """A citation into the project or organizational knowledge base (spec §12.4)."""

    document_name: str
    page_number: int | None = None
    section: str | None = None
    chunk_id: str


class GroundedMixin(BaseModel):
    """Adds classification + source_references with the SOURCE_BACKED-needs-citation rule.

    Mixed into every artifact that must declare where its content came from:
    Requirement, Epic, UserStory, Risk, Assumption.
    """

    classification: Classification
    source_references: list[SourceReference] = Field(default_factory=list)

    @model_validator(mode="after")
    def _source_backed_requires_citation(self) -> "GroundedMixin":
        if self.classification == "SOURCE_BACKED" and not self.source_references:
            raise ValueError(
                "classification=SOURCE_BACKED requires at least one source_reference "
                "(spec §12.4/§12.5; project strict-grounding rule)"
            )
        return self

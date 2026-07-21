"""Requirement Analyst Agent output schemas (spec §7.2, §13.1, §14)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.clarification import ClarificationQuestion
from app.schemas.common import GroundedMixin, SourceReference
from app.schemas.enums import RequirementCategory


class Actor(BaseModel):
    """A user persona/role identified in the source documents (spec §7.2 task 3)."""

    actor_id: str
    name: str
    description: str = ""
    source_references: list[SourceReference] = Field(default_factory=list)


class Requirement(GroundedMixin):
    """A single extracted requirement (spec §14 example, extended per §13.1)."""

    requirement_id: str
    title: str
    description: str
    category: RequirementCategory
    confidence: float = Field(ge=0.0, le=1.0)


class Contradiction(BaseModel):
    """Conflicting statements across (or within) documents (spec §7.2 task 11)."""

    contradiction_id: str
    description: str
    conflicting_requirement_ids: list[str] = Field(default_factory=list)
    source_references: list[SourceReference] = Field(default_factory=list)


class Ambiguity(BaseModel):
    """A vague or non-testable requirement (spec §7.2 task 12)."""

    ambiguity_id: str
    description: str
    related_requirement_id: str | None = None
    reason: str
    source_references: list[SourceReference] = Field(default_factory=list)


class RequirementAnalysisResult(BaseModel):
    """Full structured output of the Requirement Analyst Agent (spec §7.2 "Output")."""

    requirements: list[Requirement] = Field(default_factory=list)
    actors: list[Actor] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    contradictions: list[Contradiction] = Field(default_factory=list)
    ambiguities: list[Ambiguity] = Field(default_factory=list)
    clarification_questions: list[ClarificationQuestion] = Field(default_factory=list)


class RequirementRead(BaseModel):
    """API response schema for a persisted requirement (spec §18).

    Maps from RequirementRecord ORM model. Includes all fields except the
    internal `id` primary key and `payload_json`.
    """

    requirement_id: str
    project_id: str
    title: str
    category: str
    classification: str
    confidence: float
    workflow_run_id: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

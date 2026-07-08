"""Reviewer Agent output schema (spec §7.4, §13.12)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.enums import ReviewerDecision


class ReviewerIssue(BaseModel):
    """One finding, matching the spec §7.4 example structure exactly."""

    artifact_id: str
    issue_type: str
    description: str
    recommended_action: str


class ReviewerReport(BaseModel):
    """Spec §13.12."""

    decision: ReviewerDecision
    missing_requirements: list[str] = Field(default_factory=list)
    unsupported_claims: list[ReviewerIssue] = Field(default_factory=list)
    duplicate_stories: list[ReviewerIssue] = Field(default_factory=list)
    missing_acceptance_criteria: list[ReviewerIssue] = Field(default_factory=list)
    weak_acceptance_criteria: list[ReviewerIssue] = Field(default_factory=list)
    traceability_gaps: list[ReviewerIssue] = Field(default_factory=list)
    dependency_issues: list[ReviewerIssue] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    revision_instructions: list[ReviewerIssue] = Field(default_factory=list)

"""Shared LangGraph workflow state (spec §19, reproduced verbatim).

Kept intentionally small: references and counters only, never document or artifact
content. Documents live in the project data dir + DocumentChunkMeta; requirements,
clarifications, and plan artifacts live in SQLite (see app/models/). Agent nodes read
from and write to the database via tools — not through this state object.
"""
from __future__ import annotations

from typing import TypedDict


class ProjectWorkflowState(TypedDict):
    project_id: str
    current_stage: str
    next_action: str | None

    document_ids: list[str]
    requirement_ids: list[str]
    unresolved_question_ids: list[str]
    requirement_analysis_attempts: int

    clarification_approved: bool
    plan_version_id: str | None
    reviewer_decision: str | None
    reviewer_issue_ids: list[str]

    revision_count: int
    final_approved: bool

    errors: list[str]
    workflow_events: list[dict]

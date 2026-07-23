"""Clarification register schemas (spec §11 approval point 1, §13.2)."""
from __future__ import annotations

from pydantic import BaseModel

from app.schemas.common import SourceReference
from app.schemas.enums import ClarificationStatus, Priority


class ClarificationQuestion(BaseModel):
    """A single clarification question (spec §13.2).

    `category` is intentionally a free-text string rather than a closed enum: the spec
    defines closed categories for company-standard search (§9.2) but not for clarification
    questions, and a fixed taxonomy here would risk rejecting a legitimate category the
    Requirement Analyst needs (see docs/DAY2_UNDERSTANDING.md point 5).
    """

    question_id: str
    category: str
    question: str
    reason_for_asking: str
    related_requirement_id: str | None = None
    source_reference: SourceReference | None = None
    priority: Priority
    status: ClarificationStatus = "PENDING"
    user_answer: str | None = None


class ClarificationAnswerInfo(BaseModel):
    """One entry of `get_project_information`'s "existing clarification answers" (§9.3) —
    any question the user has already acted on (answered, deferred, or marked N/A).
    """

    question_id: str
    question: str
    status: ClarificationStatus
    user_answer: str | None = None


class ClarificationAnswerSubmission(BaseModel):
    """Request body for POST .../clarifications/answers (spec §11: answer/defer/N-A/edit)."""

    question_id: str
    status: ClarificationStatus
    user_answer: str | None = None
    question: str | None = None  # present only when the user edited the question text

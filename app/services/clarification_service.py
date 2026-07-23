"""Clarification register CRUD (spec §11, §13.2) — deterministic, no agent reasoning."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.requirement import ClarificationQuestionRecord
from app.schemas.clarification import ClarificationAnswerSubmission, ClarificationQuestion


def list_clarifications(session: Session, project_id: str) -> list[ClarificationQuestion]:
    """§11: every clarification question for a project, current status/answer included."""
    records = session.scalars(
        select(ClarificationQuestionRecord)
        .where(ClarificationQuestionRecord.project_id == project_id)
        .order_by(ClarificationQuestionRecord.id)
    ).all()
    return [ClarificationQuestion.model_validate(r.payload_json) for r in records]


def submit_answers(
    session: Session, project_id: str, answers: list[ClarificationAnswerSubmission]
) -> list[ClarificationQuestion]:
    """§11: answer/defer/mark-not-applicable/edit a batch of clarification questions.

    Raises ValueError (mapped to 404 by the API layer) if a question_id doesn't belong to
    this project — keeps the project_id filter mandatory even on writes (§12.3, §20.4).
    """
    updated: list[ClarificationQuestionRecord] = []
    for answer in answers:
        record = session.scalar(
            select(ClarificationQuestionRecord).where(
                ClarificationQuestionRecord.project_id == project_id,
                ClarificationQuestionRecord.question_id == answer.question_id,
            )
        )
        if record is None:
            raise ValueError(
                f"Clarification question '{answer.question_id}' not found "
                f"for project '{project_id}'"
            )
        payload = dict(record.payload_json)
        payload["status"] = answer.status
        payload["user_answer"] = answer.user_answer
        if answer.question is not None:
            payload["question"] = answer.question
        record.status = answer.status
        record.payload_json = payload  # reassign (not mutate) so SQLAlchemy detects the change
        updated.append(record)

    session.commit()
    for record in updated:
        session.refresh(record)
    return [ClarificationQuestion.model_validate(r.payload_json) for r in updated]

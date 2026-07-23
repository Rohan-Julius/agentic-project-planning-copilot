"""Unit tests for clarification_service (spec §11, §13.2)."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, ClarificationQuestionRecord, ProjectRecord
from app.schemas.clarification import ClarificationAnswerSubmission
from app.services import clarification_service


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine)
    db_session = session_local()
    db_session.add(ProjectRecord(project_id="PRJ-1", name="P"))
    db_session.add(
        ClarificationQuestionRecord(
            question_id="CQ-1",
            project_id="PRJ-1",
            category="auth",
            priority="High",
            status="PENDING",
            payload_json={
                "question_id": "CQ-1",
                "category": "auth",
                "question": "Which providers?",
                "reason_for_asking": "Not specified.",
                "related_requirement_id": None,
                "source_reference": None,
                "priority": "High",
                "status": "PENDING",
                "user_answer": None,
            },
        )
    )
    db_session.commit()
    yield db_session
    db_session.close()


def test_list_clarifications_returns_project_questions(session):
    result = clarification_service.list_clarifications(session, "PRJ-1")

    assert len(result) == 1
    assert result[0].question_id == "CQ-1"


def test_submit_answers_updates_status_and_answer(session):
    result = clarification_service.submit_answers(
        session,
        "PRJ-1",
        [ClarificationAnswerSubmission(question_id="CQ-1", status="ANSWERED", user_answer="Okta.")],
    )

    assert result[0].status == "ANSWERED"
    assert result[0].user_answer == "Okta."

    refetched = clarification_service.list_clarifications(session, "PRJ-1")
    assert refetched[0].status == "ANSWERED"
    assert refetched[0].user_answer == "Okta."


def test_submit_answers_can_edit_the_question_text(session):
    result = clarification_service.submit_answers(
        session,
        "PRJ-1",
        [ClarificationAnswerSubmission(
            question_id="CQ-1", status="DEFERRED", question="Edited question text?"
        )],
    )

    assert result[0].status == "DEFERRED"
    assert result[0].question == "Edited question text?"


def test_submit_answers_raises_for_unknown_question(session):
    with pytest.raises(ValueError, match="not found"):
        clarification_service.submit_answers(
            session,
            "PRJ-1",
            [ClarificationAnswerSubmission(question_id="CQ-missing", status="ANSWERED")],
        )


def test_submit_answers_is_project_isolated(session):
    """A question_id that exists but belongs to a different project must not be editable."""
    session.add(ProjectRecord(project_id="PRJ-2", name="P2"))
    session.commit()

    with pytest.raises(ValueError, match="not found"):
        clarification_service.submit_answers(
            session,
            "PRJ-2",
            [ClarificationAnswerSubmission(question_id="CQ-1", status="ANSWERED")],
        )

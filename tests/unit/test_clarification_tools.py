"""Unit tests for get_clarification_answers tool (spec §9.6)."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, ClarificationQuestionRecord, ProjectRecord
from app.tools.project_tools import get_clarification_answers


def _session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _seed(session_factory, project_id, question_id, status="PENDING"):
    session = session_factory()
    session.add(ProjectRecord(project_id=project_id, name="P"))
    session.add(
        ClarificationQuestionRecord(
            question_id=question_id,
            project_id=project_id,
            category="auth",
            priority="High",
            status=status,
            payload_json={
                "question_id": question_id,
                "category": "auth",
                "question": "Which providers?",
                "reason_for_asking": "Not specified.",
                "related_requirement_id": None,
                "source_reference": None,
                "priority": "High",
                "status": status,
                "user_answer": None,
            },
        )
    )
    session.commit()
    session.close()


def test_get_clarification_answers_returns_project_questions():
    session_factory = _session_factory()
    _seed(session_factory, "PRJ-1", "CQ-1")

    result = get_clarification_answers("PRJ-1", session_factory=session_factory)

    assert len(result) == 1
    assert result[0].question_id == "CQ-1"
    assert result[0].status == "PENDING"


def test_get_clarification_answers_is_project_isolated():
    session_factory = _session_factory()
    _seed(session_factory, "PRJ-A", "CQ-A")
    _seed(session_factory, "PRJ-B", "CQ-B")

    result = get_clarification_answers("PRJ-A", session_factory=session_factory)

    assert [q.question_id for q in result] == ["CQ-A"]

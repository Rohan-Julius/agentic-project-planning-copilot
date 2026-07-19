"""`get_project_information` tool tests (spec §9.3)."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.requirement import ClarificationQuestionRecord
from app.schemas.project import ProjectCreate
from app.services import project_service
from app.tools.project_tools import get_project_information


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _create_project(session_factory) -> str:
    session = session_factory()
    project = project_service.create_project(
        session,
        ProjectCreate(
            name="Leave Management",
            description="Employee leave tracking.",
            team_composition="2 backend, 1 frontend",
            target_platforms=["web"],
            technology_constraints=["must use PostgreSQL"],
            expected_duration_weeks=8,
        ),
    )
    project_id = project.project_id
    session.close()
    return project_id


def _add_clarification(session_factory, project_id, status, user_answer=None) -> str:
    session = session_factory()
    question_id = f"CQ-{status}"
    session.add(
        ClarificationQuestionRecord(
            question_id=question_id,
            project_id=project_id,
            category="security",
            priority="High",
            status=status,
            payload_json={
                "question_id": question_id,
                "category": "security",
                "question": "Which identity provider should be used?",
                "reason_for_asking": "Authentication is mentioned but no provider is named.",
                "priority": "High",
                "status": status,
                "user_answer": user_answer,
            },
        )
    )
    session.commit()
    session.close()
    return question_id


def test_get_project_information_returns_core_fields(session_factory):
    project_id = _create_project(session_factory)

    info = get_project_information(project_id, session_factory=session_factory)

    assert info.project_id == project_id
    assert info.name == "Leave Management"
    assert info.team_composition == "2 backend, 1 frontend"
    assert info.target_platforms == ["web"]
    assert info.technology_constraints == ["must use PostgreSQL"]
    assert info.expected_duration_weeks == 8


def test_get_project_information_includes_only_acted_on_clarifications(session_factory):
    project_id = _create_project(session_factory)
    _add_clarification(session_factory, project_id, status="PENDING")
    _add_clarification(session_factory, project_id, status="ANSWERED", user_answer="Okta")

    info = get_project_information(project_id, session_factory=session_factory)

    assert len(info.existing_clarification_answers) == 1
    answer = info.existing_clarification_answers[0]
    assert answer.status == "ANSWERED"
    assert answer.user_answer == "Okta"


def test_get_project_information_unknown_project_raises(session_factory):
    with pytest.raises(ValueError):
        get_project_information("does-not-exist", session_factory=session_factory)

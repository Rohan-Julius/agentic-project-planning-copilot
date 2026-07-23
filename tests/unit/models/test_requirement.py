"""Unit tests for RequirementRecord and ClarificationQuestionRecord ORM models."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.requirement import RequirementRecord, ClarificationQuestionRecord
from app.models.base import Base


def test_requirement_record_create():
    """RequirementRecord can be created and saved."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        req = RequirementRecord(
            requirement_id="REQ-001",
            project_id="PRJ-001",
            title="User authentication",
            category="functional",
            classification="SOURCE_BACKED",
            confidence=0.95,
            payload_json={"description": "System must support OAuth2"},
            workflow_run_id="RUN-001",
        )
        session.add(req)
        session.commit()

        fetched = session.query(RequirementRecord).filter_by(requirement_id="REQ-001").first()
        assert fetched.title == "User authentication"
        assert fetched.project_id == "PRJ-001"


def test_clarification_question_record_create():
    """ClarificationQuestionRecord can be created and saved."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        q = ClarificationQuestionRecord(
            question_id="Q-001",
            project_id="PRJ-001",
            category="technical",
            priority="High",
            status="PENDING",
            payload_json={
                "question": "Which OAuth2 providers are supported?",
                "reason_for_asking": "Authentication details not specified",
            },
        )
        session.add(q)
        session.commit()

        fetched = session.query(ClarificationQuestionRecord).filter_by(question_id="Q-001").first()
        assert fetched.status == "PENDING"

"""`get_project_information` tool tests (spec §9.3)."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.plan_artifact import PlanArtifactVersion
from app.models.requirement import ClarificationQuestionRecord, RequirementRecord
from app.schemas.planning import ProjectPlan, ProjectSummary, Scope
from app.schemas.project import ProjectCreate
from app.schemas.requirement import Requirement
from app.services import project_service
from app.tools.project_tools import get_project_information, get_requirements, save_planning_artifacts


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


# --- get_requirements (Day 11: Planning Agent's approved-input boundary, DESIGN.md §8.3) ---

def _add_requirement(
    session_factory, project_id, requirement_id="REQ-1", classification="SOURCE_BACKED"
) -> None:
    session = session_factory()
    source_references = (
        [
            {
                "document_name": "support-notes.txt",
                "page_number": 1,
                "section": "Overview",
                "chunk_id": "DOC-1-CH-001",
            }
        ]
        if classification == "SOURCE_BACKED"
        else []
    )
    session.add(
        RequirementRecord(
            requirement_id=requirement_id,
            project_id=project_id,
            workflow_run_id="RUN-1",
            title="Multi-channel support",
            category="functional",
            classification=classification,
            confidence=0.9,
            payload_json={
                "requirement_id": requirement_id,
                "title": "Multi-channel support",
                "description": "The assistant must support chat and email.",
                "category": "functional",
                "classification": classification,
                "confidence": 0.9,
                "source_references": source_references,
            },
        )
    )
    session.commit()
    session.close()


def test_get_requirements_returns_all_for_project(session_factory):
    project_id = _create_project(session_factory)
    _add_requirement(session_factory, project_id, requirement_id="REQ-1")
    _add_requirement(session_factory, project_id, requirement_id="REQ-2", classification="ASSUMPTION")

    requirements = get_requirements(project_id, session_factory=session_factory)

    assert len(requirements) == 2
    assert all(isinstance(r, Requirement) for r in requirements)
    assert {r.requirement_id for r in requirements} == {"REQ-1", "REQ-2"}


def test_get_requirements_project_isolation(session_factory):
    project_a = _create_project(session_factory)
    project_b = _create_project(session_factory)
    _add_requirement(session_factory, project_a, requirement_id="REQ-A")
    _add_requirement(session_factory, project_b, requirement_id="REQ-B")

    requirements = get_requirements(project_a, session_factory=session_factory)

    assert [r.requirement_id for r in requirements] == ["REQ-A"]


def test_get_requirements_empty_project_returns_empty_list(session_factory):
    project_id = _create_project(session_factory)

    requirements = get_requirements(project_id, session_factory=session_factory)

    assert requirements == []


# --- save_planning_artifacts (Day 12: plan persistence and versioning, spec §9.7, §22) ---

def _minimal_plan() -> ProjectPlan:
    return ProjectPlan(
        summary=ProjectSummary(business_problem="X", proposed_solution="Y"),
        scope=Scope(in_scope=["A"]),
    )


def test_save_planning_artifacts_creates_first_version(session_factory):
    project_id = _create_project(session_factory)

    version_id = save_planning_artifacts(project_id, _minimal_plan(), session_factory=session_factory)

    session = session_factory()
    row = session.execute(
        select(PlanArtifactVersion).where(PlanArtifactVersion.version_id == version_id)
    ).scalar_one()
    session.close()
    assert row.project_id == project_id
    assert row.version_number == 1
    assert row.is_current is True
    assert row.plan_json["summary"]["business_problem"] == "X"


def test_save_planning_artifacts_increments_version_and_unsets_previous_current(session_factory):
    project_id = _create_project(session_factory)
    save_planning_artifacts(project_id, _minimal_plan(), session_factory=session_factory)
    second_id = save_planning_artifacts(project_id, _minimal_plan(), session_factory=session_factory)

    session = session_factory()
    rows = session.execute(
        select(PlanArtifactVersion).where(PlanArtifactVersion.project_id == project_id)
    ).scalars().all()
    session.close()

    assert len(rows) == 2
    current = [r for r in rows if r.is_current]
    assert len(current) == 1
    assert current[0].version_id == second_id
    assert current[0].version_number == 2

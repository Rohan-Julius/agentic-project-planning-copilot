"""Project-context tool (spec §9.3, §9.4, §9.5) — the agent<->project-metadata boundary.

`get_project_information` ships on Day 6; `save_requirements`,
`save_clarification_questions` (Day 9), `get_clarification_answers`, and
`save_planning_artifacts` (Days 10/12) per PROJECT_PLAN.md.
"""
from __future__ import annotations

import uuid
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.database.session import get_sessionmaker
from app.models.requirement import ClarificationQuestionRecord, RequirementRecord
from app.schemas.clarification import ClarificationAnswerInfo, ClarificationQuestion
from app.schemas.project import ProjectInfo
from app.schemas.requirement import RequirementAnalysisResult
from app.services import project_service


def get_project_information(
    project_id: str,
    *,
    session_factory: Callable[[], Session] | sessionmaker | None = None,
) -> ProjectInfo:
    """§9.3. Raises `ValueError` for an unknown project_id — callers (agents/tools layer)
    are expected to have already validated the project exists via workflow state.
    """
    session_factory = session_factory or get_sessionmaker()
    session = session_factory()
    try:
        project = project_service.get_project(session, project_id)
        if project is None:
            raise ValueError(f"Project '{project_id}' not found")

        # "Existing clarification answers" (§9.3) — any question the user has already
        # acted on, not just ones with a filled-in text answer (deferred/N-A count too).
        acted_on = session.scalars(
            select(ClarificationQuestionRecord).where(
                ClarificationQuestionRecord.project_id == project_id,
                ClarificationQuestionRecord.status != "PENDING",
            )
        ).all()

        return ProjectInfo(
            project_id=project.project_id,
            name=project.name,
            description=project.description,
            methodology=project.methodology,
            expected_duration_weeks=project.expected_duration_weeks,
            team_composition=project.team_composition,
            target_platforms=project.target_platforms,
            technology_constraints=project.technology_constraints,
            existing_clarification_answers=[
                ClarificationAnswerInfo(
                    question_id=row.question_id,
                    question=row.payload_json.get("question", ""),
                    status=row.status,
                    user_answer=row.payload_json.get("user_answer"),
                )
                for row in acted_on
            ],
        )
    finally:
        session.close()


def save_requirements(
    project_id: str,
    analysis_result: RequirementAnalysisResult,
    workflow_run_id: str,
    *,
    session_factory: Callable[[], Session] | sessionmaker | None = None,
) -> None:
    """Save extracted requirements from Requirement Analyst Agent (spec §9.4).

    For each requirement in analysis_result:
    1. Create RequirementRecord with full payload
    2. Commit to database
    3. All saved with project_id (mandatory isolation per §12.3, §20.4)

    Args:
        project_id: must match the project being analyzed (FK constraint enforces isolation)
        analysis_result: RequirementAnalysisResult from Requirement Analyst Agent
        workflow_run_id: the workflow run ID for audit trail (§21)
        session_factory: SQLAlchemy session factory (injected for tests; uses default if None)
    """
    session_factory = session_factory or get_sessionmaker()
    session = session_factory()
    try:
        for req_pydantic in analysis_result.requirements:
            # Create ORM record with full payload (spec §22 versioning)
            req_record = RequirementRecord(
                requirement_id=req_pydantic.requirement_id,
                project_id=project_id,
                workflow_run_id=workflow_run_id,
                title=req_pydantic.title,
                category=req_pydantic.category,
                classification=req_pydantic.classification,
                confidence=req_pydantic.confidence,
                payload_json=req_pydantic.model_dump(),  # Full Pydantic payload
            )
            session.add(req_record)
        session.commit()
    finally:
        session.close()


def save_clarification_questions(
    project_id: str,
    analysis_result: RequirementAnalysisResult,
    workflow_run_id: str,
    *,
    session_factory: Callable[[], Session] | sessionmaker | None = None,
) -> None:
    """Save clarification questions from Requirement Analyst Agent (spec §9.5).

    Each clarification question is saved with:
    - status = "PENDING" (awaiting human gate 1 review per §11)
    - Full payload for later retrieval
    - project_id isolation (§20.4)

    Args:
        project_id: project being analyzed
        analysis_result: RequirementAnalysisResult containing clarification_questions
        workflow_run_id: audit trail reference
        session_factory: SQLAlchemy session factory (injected for tests; uses default if None)
    """
    session_factory = session_factory or get_sessionmaker()
    session = session_factory()
    try:
        for q_pydantic in analysis_result.clarification_questions:
            q_record = ClarificationQuestionRecord(
                question_id=q_pydantic.question_id,
                project_id=project_id,
                category=q_pydantic.category,
                priority=q_pydantic.priority,
                status="PENDING",  # Initial status; user can change via §11 gate
                payload_json=q_pydantic.model_dump(),  # Full Pydantic payload
            )
            session.add(q_record)
        session.commit()
    finally:
        session.close()


def get_clarification_answers(
    project_id: str,
    *,
    session_factory: Callable[[], Session] | sessionmaker | None = None,
) -> list[ClarificationQuestion]:
    """§9.6 — every clarification question for a project with its current status/answer.
    Used by later agents (Planning Agent, Day 11+) to consume human clarification input.
    """
    session_factory = session_factory or get_sessionmaker()
    session = session_factory()
    try:
        records = session.scalars(
            select(ClarificationQuestionRecord).where(
                ClarificationQuestionRecord.project_id == project_id
            )
        ).all()
        return [ClarificationQuestion.model_validate(r.payload_json) for r in records]
    finally:
        session.close()

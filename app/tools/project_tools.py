"""Project-context tool (spec §9.3) — the agent<->project-metadata boundary.

Only `get_project_information` ships on Day 6; `save_requirements`,
`save_clarification_questions`, `get_clarification_answers`, and `save_planning_artifacts`
follow on Days 9/10/12 per PROJECT_PLAN.md.
"""
from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.database.session import get_sessionmaker
from app.models.requirement import ClarificationQuestionRecord
from app.schemas.clarification import ClarificationAnswerInfo
from app.schemas.project import ProjectInfo
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

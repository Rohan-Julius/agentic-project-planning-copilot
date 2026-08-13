"""Deterministic per-project status aggregation for the dashboard screen (spec §16.1).

Pure read-side aggregation over data other services already own (documents, requirements,
clarifications, plan artifacts, workflow runs) — no new business logic and no agent
involvement; every field is either a stored value or a mechanical derivation of one. All
queries are scoped by `project_id` (§12.3, §20.4) so one project's activity never appears
on another's row.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document import DocumentRecord
from app.models.plan_artifact import PlanArtifactVersion
from app.models.project import ProjectRecord
from app.models.requirement import ClarificationQuestionRecord, RequirementRecord
from app.models.workflow import WorkflowRun
from app.schemas.dashboard import DashboardProjectRead


def _count(session: Session, model, project_id: str) -> int:
    return session.scalar(
        select(func.count()).select_from(model).where(model.project_id == project_id)
    ) or 0


def _requirement_analysis_status(session: Session, project_id: str) -> str:
    if _count(session, RequirementRecord, project_id) > 0:
        return "COMPLETE"
    if _count(session, WorkflowRun, project_id) > 0:
        return "IN_PROGRESS"
    return "NOT_STARTED"


def _clarification_status(session: Session, project_id: str) -> str:
    statuses = session.scalars(
        select(ClarificationQuestionRecord.status).where(
            ClarificationQuestionRecord.project_id == project_id
        )
    ).all()
    if not statuses:
        return "NOT_STARTED"
    if any(status == "PENDING" for status in statuses):
        return "PENDING_REVIEW"
    return "RESOLVED"


def _current_plan_version(session: Session, project_id: str) -> PlanArtifactVersion | None:
    return session.scalar(
        select(PlanArtifactVersion).where(
            PlanArtifactVersion.project_id == project_id,
            PlanArtifactVersion.is_current.is_(True),
        )
    )


def _planning_status(version: PlanArtifactVersion | None) -> str:
    return "COMPLETE" if version is not None else "NOT_STARTED"


def _reviewer_status(version: PlanArtifactVersion | None) -> str:
    if version is None or version.reviewer_decision is None:
        return "NOT_STARTED"
    return version.reviewer_decision


def _approval_status(session: Session, project_id: str) -> str:
    latest_run = session.scalar(
        select(WorkflowRun)
        .where(WorkflowRun.project_id == project_id)
        .order_by(WorkflowRun.started_at.desc())
    )
    return "APPROVED" if latest_run is not None and latest_run.final_approved else "NOT_APPROVED"


def get_dashboard(session: Session) -> list[DashboardProjectRead]:
    """One `DashboardProjectRead` per project (spec §16.1), newest activity first isn't
    required by the spec — returned in whatever order `ProjectRecord` rows come back in.
    """
    rows: list[DashboardProjectRead] = []
    for project in session.scalars(select(ProjectRecord)):
        version = _current_plan_version(session, project.project_id)
        rows.append(
            DashboardProjectRead(
                project_id=project.project_id,
                name=project.name,
                status=project.status,
                document_count=_count(session, DocumentRecord, project.project_id),
                requirement_analysis_status=_requirement_analysis_status(
                    session, project.project_id
                ),
                clarification_status=_clarification_status(session, project.project_id),
                planning_status=_planning_status(version),
                reviewer_status=_reviewer_status(version),
                approval_status=_approval_status(session, project.project_id),
            )
        )
    return rows

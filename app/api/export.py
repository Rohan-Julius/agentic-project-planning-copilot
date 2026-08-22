"""Export endpoints (spec §16.8, §17, §18, §20.2, §20.5).

Deterministic; regenerated on demand from the current persisted plan — never served from a
stale file. Approval status is read from the latest WorkflowRun.final_approved and never
hardcoded to "approved" (§20.5): export itself is allowed at any time so a PM can preview a
draft plan, but the JSON/Markdown output is always honestly labeled DRAFT_PENDING_APPROVAL
until the plan has actually been approved via POST .../plan/approve.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database.session import get_session
from app.models.plan_artifact import PlanArtifactVersion
from app.models.workflow import WorkflowRun
from app.schemas.planning import ProjectPlan
from app.schemas.reviewer import ReviewerReport
from app.services import project_service
from app.services.export_service import (
    build_zip_bytes,
    write_docx_file,
    write_jira_csv_file,
    write_json_file,
    write_markdown_file,
    write_reviewer_report_file,
)

router = APIRouter(prefix="/projects/{project_id}/export", tags=["export"])


def _require_project(session: Session, project_id: str) -> None:
    if project_service.get_project(session, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


def _require_plan(session: Session, project_id: str) -> ProjectPlan:
    version = session.scalar(
        select(PlanArtifactVersion).where(
            PlanArtifactVersion.project_id == project_id,
            PlanArtifactVersion.is_current.is_(True),
        )
    )
    if version is None:
        raise HTTPException(status_code=404, detail=f"No plan generated yet for project '{project_id}'")
    return ProjectPlan.model_validate(version.plan_json)


def _is_final_approved(session: Session, project_id: str) -> bool:
    run = session.scalar(
        select(WorkflowRun)
        .where(WorkflowRun.project_id == project_id)
        .order_by(WorkflowRun.started_at.desc())
    )
    return bool(run and run.final_approved)


def _current_reviewer_report(session: Session, project_id: str) -> ReviewerReport | None:
    version = session.scalar(
        select(PlanArtifactVersion).where(
            PlanArtifactVersion.project_id == project_id,
            PlanArtifactVersion.is_current.is_(True),
        )
    )
    if version is None or version.reviewer_report_json is None:
        return None
    return ReviewerReport.model_validate(version.reviewer_report_json)


@router.get("/json")
def export_json(
    project_id: str,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    _require_project(session, project_id)
    plan = _require_plan(session, project_id)
    approved = _is_final_approved(session, project_id)
    path = write_json_file(project_id, plan, approved=approved, export_dir=settings.exports_dir)
    return FileResponse(path, media_type="application/json", filename=f"{project_id}-plan.json")


@router.get("/markdown")
def export_markdown(
    project_id: str,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    _require_project(session, project_id)
    plan = _require_plan(session, project_id)
    approved = _is_final_approved(session, project_id)
    path = write_markdown_file(project_id, plan, approved=approved, export_dir=settings.exports_dir)
    return FileResponse(path, media_type="text/markdown", filename=f"{project_id}-plan.md")


@router.get("/docx")
def export_docx(
    project_id: str,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    _require_project(session, project_id)
    plan = _require_plan(session, project_id)
    approved = _is_final_approved(session, project_id)
    path = write_docx_file(project_id, plan, approved=approved, export_dir=settings.exports_dir)
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"{project_id}-plan.docx",
    )


@router.get("/jira-csv")
def export_jira_csv_endpoint(
    project_id: str,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    _require_project(session, project_id)
    plan = _require_plan(session, project_id)
    path = write_jira_csv_file(project_id, plan, export_dir=settings.exports_dir)
    return FileResponse(path, media_type="text/csv", filename=f"{project_id}-jira.csv")


@router.get("/zip")
def export_zip(
    project_id: str,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    _require_project(session, project_id)
    plan = _require_plan(session, project_id)
    approved = _is_final_approved(session, project_id)
    paths = {
        "json": write_json_file(project_id, plan, approved=approved, export_dir=settings.exports_dir),
        "markdown": write_markdown_file(project_id, plan, approved=approved, export_dir=settings.exports_dir),
        "jira_csv": write_jira_csv_file(project_id, plan, export_dir=settings.exports_dir),
        "docx": write_docx_file(project_id, plan, approved=approved, export_dir=settings.exports_dir),
    }
    report = _current_reviewer_report(session, project_id)
    if report is not None:
        paths["reviewer_report"] = write_reviewer_report_file(
            project_id, report, export_dir=settings.exports_dir
        )
    return Response(
        content=build_zip_bytes(paths),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{project_id}-export.zip"'},
    )

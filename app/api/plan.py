"""Plan read + approval endpoints (spec §18, §9.7, §11 approval point 2)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.database.session import get_session, get_sessionmaker
from app.models.plan_artifact import PlanArtifactVersion
from app.models.workflow import WorkflowRun
from app.schemas.planning import PlanVersionSummary, ProjectPlan
from app.schemas.workflow import WorkflowRunRead
from app.services import project_service
from app.services.vector_service import VectorService, get_vector_service
from app.workflow import engine
from app.workflow.checkpointer import get_checkpointer
from app.workflow.engine import STATUS_WAITING_FOR_HUMAN_INPUT
from app.workflow.routes import NODE_FINAL_GATE

router = APIRouter(prefix="/projects/{project_id}/plan", tags=["plan"])


def _require_project(session: Session, project_id: str) -> None:
    if project_service.get_project(session, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


def _require_project_dependency(
    project_id: str, session: Session = Depends(get_session)
) -> None:
    """Same check as _require_project, structured as a FastAPI dependency (Day 23) so it
    resolves before sibling Depends() params like get_vector_service — see Day 17's
    dependency-ordering finding, docs/PROJECT_PLAN.md."""
    _require_project(session, project_id)


@router.get("", response_model=ProjectPlan)
def get_plan(project_id: str, session: Session = Depends(get_session)) -> ProjectPlan:
    """Return the current plan version for a project (spec §9.7, §18). 404 if no plan has
    been generated yet.
    """
    _require_project(session, project_id)
    version = session.scalar(
        select(PlanArtifactVersion).where(
            PlanArtifactVersion.project_id == project_id,
            PlanArtifactVersion.is_current.is_(True),
        )
    )
    if version is None:
        raise HTTPException(status_code=404, detail=f"No plan generated yet for project '{project_id}'")
    return ProjectPlan.model_validate(version.plan_json)


def _to_version_summary(version: PlanArtifactVersion) -> PlanVersionSummary:
    return PlanVersionSummary(
        version_id=version.version_id,
        version_number=version.version_number,
        model=version.model,
        prompt_version=version.prompt_version,
        reviewer_decision=version.reviewer_decision,
        is_current=version.is_current,
        generated_at=version.generated_at,
    )


@router.get("/versions", response_model=list[PlanVersionSummary])
def list_plan_versions(project_id: str, session: Session = Depends(get_session)) -> list[PlanVersionSummary]:
    """List every plan version for a project, newest first (spec §22 — the version-history
    list a comparison UI would page through)."""
    _require_project(session, project_id)
    versions = session.scalars(
        select(PlanArtifactVersion)
        .where(PlanArtifactVersion.project_id == project_id)
        .order_by(PlanArtifactVersion.version_number.desc())
    ).all()
    return [_to_version_summary(v) for v in versions]


@router.get("/versions/{version_id}", response_model=ProjectPlan)
def get_plan_version(
    project_id: str, version_id: str, session: Session = Depends(get_session)
) -> ProjectPlan:
    """Full plan JSON for one specific historical version (spec §22 'previous output, new
    output' comparison) — not just the current one, unlike GET .../plan."""
    _require_project(session, project_id)
    version = session.scalar(
        select(PlanArtifactVersion).where(
            PlanArtifactVersion.project_id == project_id,
            PlanArtifactVersion.version_id == version_id,
        )
    )
    if version is None:
        raise HTTPException(
            status_code=404,
            detail=f"Plan version '{version_id}' not found for project '{project_id}'",
        )
    return ProjectPlan.model_validate(version.plan_json)


@router.post("/approve", response_model=WorkflowRunRead)
def approve_plan(
    project_id: str,
    session: Session = Depends(get_session),
    _project_exists: None = Depends(_require_project_dependency),
    checkpointer: BaseCheckpointSaver = Depends(get_checkpointer),
    session_factory: sessionmaker = Depends(get_sessionmaker),
    vector_service: VectorService = Depends(get_vector_service),
):
    """§11 approval point 2: human approval of the final project plan. This is the only
    place `final_approved` is ever set True (§20.5) — no agent path sets it, mirroring
    clarifications/approve's authority pattern exactly.
    """
    run = session.scalar(
        select(WorkflowRun)
        .where(WorkflowRun.project_id == project_id)
        .order_by(WorkflowRun.started_at.desc())
    )
    if run is None:
        raise HTTPException(status_code=404, detail=f"No workflow run for project '{project_id}'")
    if run.status != STATUS_WAITING_FOR_HUMAN_INPUT:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Workflow run '{run.workflow_run_id}' is not waiting for human input "
                f"(status: {run.status})"
            ),
        )

    pending_gate = engine.get_pending_gate_stage(
        checkpointer, run.workflow_run_id, session_factory, vector_service
    )
    if pending_gate != NODE_FINAL_GATE:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Workflow run '{run.workflow_run_id}' is not waiting at the final approval "
                f"gate (currently paused at: {pending_gate!r}) — nothing to approve here."
            ),
        )

    updated_run = engine.resume_workflow(
        session,
        checkpointer,
        run.workflow_run_id,
        resume_value="approved",
        session_factory=session_factory,
        vector_service=vector_service,
        state_patch={"final_approved": True},
    )
    return WorkflowRunRead.model_validate(updated_run)

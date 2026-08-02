"""Plan read + approval endpoints (spec §18, §9.7, §11 approval point 2)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.database.session import get_session, get_sessionmaker
from app.models.plan_artifact import PlanArtifactVersion
from app.models.workflow import WorkflowRun
from app.schemas.planning import ProjectPlan
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


@router.post("/approve", response_model=WorkflowRunRead)
def approve_plan(
    project_id: str,
    session: Session = Depends(get_session),
    checkpointer: BaseCheckpointSaver = Depends(get_checkpointer),
    session_factory: sessionmaker = Depends(get_sessionmaker),
    vector_service: VectorService = Depends(get_vector_service),
):
    """§11 approval point 2: human approval of the final project plan. This is the only
    place `final_approved` is ever set True (§20.5) — no agent path sets it, mirroring
    clarifications/approve's authority pattern exactly.
    """
    _require_project(session, project_id)
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

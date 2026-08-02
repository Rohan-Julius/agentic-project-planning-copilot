"""Workflow endpoints (spec §18): start / status / events."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.database.session import get_session, get_sessionmaker
from app.models.workflow import WorkflowEvent, WorkflowRun
from app.schemas.workflow import WorkflowEventRead, WorkflowRunRead
from app.services import project_service
from app.services.vector_service import VectorService, get_vector_service
from app.workflow import engine
from app.workflow.checkpointer import get_checkpointer
from app.workflow.engine import STATUS_RUNNING, STATUS_WAITING_FOR_HUMAN_INPUT

router = APIRouter(prefix="/projects/{project_id}/workflow", tags=["workflow"])


def _require_project(session: Session, project_id: str) -> None:
    if project_service.get_project(session, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.post("/start", response_model=WorkflowRunRead)
def start_workflow(
    project_id: str,
    session: Session = Depends(get_session),
    checkpointer: BaseCheckpointSaver = Depends(get_checkpointer),
    session_factory: sessionmaker = Depends(get_sessionmaker),
    vector_service: VectorService = Depends(get_vector_service),
):
    _require_project(session, project_id)
    existing = session.scalar(
        select(WorkflowRun)
        .where(WorkflowRun.project_id == project_id)
        .order_by(WorkflowRun.started_at.desc())
    )
    if existing is not None and existing.status in (STATUS_RUNNING, STATUS_WAITING_FOR_HUMAN_INPUT):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Workflow run '{existing.workflow_run_id}' is already {existing.status} for "
                f"project '{project_id}' — wait for it to finish or reach a human gate before "
                "starting another run."
            ),
        )
    run = engine.start_workflow(session, checkpointer, project_id, session_factory, vector_service)
    return WorkflowRunRead.model_validate(run)


@router.get("/status", response_model=WorkflowRunRead)
def workflow_status(
    project_id: str,
    session: Session = Depends(get_session),
    checkpointer: BaseCheckpointSaver = Depends(get_checkpointer),
    session_factory: sessionmaker = Depends(get_sessionmaker),
    vector_service: VectorService = Depends(get_vector_service),
):
    _require_project(session, project_id)
    run = session.scalar(
        select(WorkflowRun)
        .where(WorkflowRun.project_id == project_id)
        .order_by(WorkflowRun.started_at.desc())
    )
    if run is None:
        raise HTTPException(status_code=404, detail=f"No workflow run for project '{project_id}'")

    pending_gate = None
    if run.status == STATUS_WAITING_FOR_HUMAN_INPUT:
        pending_gate = engine.get_pending_gate_stage(
            checkpointer, run.workflow_run_id, session_factory, vector_service
        )
    return WorkflowRunRead.model_validate(run).model_copy(update={"pending_gate": pending_gate})


@router.get("/events", response_model=list[WorkflowEventRead])
def workflow_events(project_id: str, session: Session = Depends(get_session)):
    """Events for the project's *latest* workflow run only (spec §16.4's execution screen
    shows one run's live progress, not a jumbled history of every past attempt — a project
    re-run after an earlier failure must not have that failure's events mixed into the
    current run's log).
    """
    _require_project(session, project_id)
    latest_run = session.scalar(
        select(WorkflowRun)
        .where(WorkflowRun.project_id == project_id)
        .order_by(WorkflowRun.started_at.desc())
    )
    if latest_run is None:
        return []
    events = session.scalars(
        select(WorkflowEvent)
        .where(WorkflowEvent.workflow_run_id == latest_run.workflow_run_id)
        .order_by(WorkflowEvent.timestamp)
    ).all()
    return [WorkflowEventRead.model_validate(e) for e in events]

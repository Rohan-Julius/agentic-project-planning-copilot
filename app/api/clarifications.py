"""Clarification workflow endpoints (spec §11 approval point 1, §13.2, §18)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.database.session import get_session, get_sessionmaker
from app.models.workflow import WorkflowRun
from app.schemas.clarification import ClarificationAnswerSubmission, ClarificationQuestion
from app.schemas.workflow import WorkflowRunRead
from app.services import clarification_service, project_service
from app.services.vector_service import VectorService, get_vector_service
from app.workflow import engine
from app.workflow.checkpointer import get_checkpointer
from app.workflow.engine import STATUS_WAITING_FOR_HUMAN_INPUT
from app.workflow.routes import NODE_CLARIFICATION_GATE

router = APIRouter(prefix="/projects/{project_id}/clarifications", tags=["clarifications"])


def _require_project(session: Session, project_id: str) -> None:
    if project_service.get_project(session, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.get("", response_model=list[ClarificationQuestion])
def list_clarifications(project_id: str, session: Session = Depends(get_session)):
    _require_project(session, project_id)
    return clarification_service.list_clarifications(session, project_id)


@router.post("/answers", response_model=list[ClarificationQuestion])
def submit_answers(
    project_id: str,
    answers: list[ClarificationAnswerSubmission],
    session: Session = Depends(get_session),
):
    _require_project(session, project_id)
    try:
        return clarification_service.submit_answers(session, project_id, answers)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/approve", response_model=WorkflowRunRead)
def approve_clarifications(
    project_id: str,
    session: Session = Depends(get_session),
    checkpointer: BaseCheckpointSaver = Depends(get_checkpointer),
    session_factory: sessionmaker = Depends(get_sessionmaker),
    vector_service: VectorService = Depends(get_vector_service),
):
    """§11 approval point 1: human approval of the collected clarification answers.
    Unconditional once called — deferred/not-applicable questions are legitimate outcomes,
    not blockers (the user explicitly choosing to proceed with unresolved items, per §11).
    Never called automatically anywhere in this codebase (§20.5).
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
    if pending_gate != NODE_CLARIFICATION_GATE:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Workflow run '{run.workflow_run_id}' is not waiting at the clarification "
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
        state_patch={"clarification_approved": True},
    )
    return WorkflowRunRead.model_validate(updated_run)

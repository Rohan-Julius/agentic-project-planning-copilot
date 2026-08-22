"""Plan read + approval endpoints (spec §18, §9.7, §11 approval point 2)."""
from __future__ import annotations

import uuid

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


def _reset_approval_if_needed(session: Session, project_id: str) -> None:
    """§20.5 guardrail: a new plan version from selective regeneration has not been reviewed
    or approved by anyone — if the latest WorkflowRun was previously approved, it must not
    keep silently reporting "approved" for content nobody has actually seen yet. Mirrors the
    exact pattern approve_plan uses to *set* this flag, in reverse.
    """
    run = session.scalar(
        select(WorkflowRun)
        .where(WorkflowRun.project_id == project_id)
        .order_by(WorkflowRun.started_at.desc())
    )
    if run is not None and run.final_approved:
        run.final_approved = False
        session.commit()


@router.post("/regenerate/sprint-plan", response_model=ProjectPlan)
def regenerate_sprint_plan_endpoint(
    project_id: str,
    session: Session = Depends(get_session),
    _project_exists: None = Depends(_require_project_dependency),
    session_factory: sessionmaker = Depends(get_sessionmaker),
) -> ProjectPlan:
    """Regenerate only the sprint plan against the current plan's existing stories (§32
    'selective artifact regeneration') — not a full Planning re-run.
    """
    from app.agents.planning import regenerate_sprint_plan
    from app.agents.runner import AgentError

    try:
        updated_plan = regenerate_sprint_plan(
            project_id, f"regen-{uuid.uuid4().hex[:12]}", session_factory=session_factory,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except AgentError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    _reset_approval_if_needed(session, project_id)
    return updated_plan


@router.post("/regenerate/tasks-deps-raid", response_model=ProjectPlan)
def regenerate_tasks_deps_raid_endpoint(
    project_id: str,
    session: Session = Depends(get_session),
    _project_exists: None = Depends(_require_project_dependency),
    session_factory: sessionmaker = Depends(get_sessionmaker),
    vector_service: VectorService = Depends(get_vector_service),
) -> ProjectPlan:
    """Regenerate only technical tasks, dependencies, and the RAID log against the current
    plan's existing epics/stories (§32 'selective artifact regeneration').
    """
    from app.agents.planning import regenerate_tasks_deps_raid
    from app.agents.runner import AgentError

    try:
        updated_plan = regenerate_tasks_deps_raid(
            project_id, f"regen-{uuid.uuid4().hex[:12]}",
            session_factory=session_factory, vector_service=vector_service,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except AgentError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    _reset_approval_if_needed(session, project_id)
    return updated_plan


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

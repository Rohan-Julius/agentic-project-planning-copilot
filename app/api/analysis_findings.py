"""Contradictions/ambiguities read endpoints (Day 23, spec §13.1, §18 — previously generated
by the Requirement Analyst Agent but not exposed anywhere; only clarification questions and
requirements were queryable). Filters by project_id for isolation (§12.3, §20.4).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.models.requirement import AmbiguityRecord, ContradictionRecord
from app.schemas.requirement import Ambiguity, Contradiction
from app.services import project_service

router = APIRouter(prefix="/projects/{project_id}", tags=["analysis-findings"])


def _require_project(session: Session, project_id: str) -> None:
    if project_service.get_project(session, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.get("/contradictions", response_model=list[Contradiction])
def get_contradictions(project_id: str, session: Session = Depends(get_session)) -> list[Contradiction]:
    """Retrieve all contradictions detected for a project (spec §13.1, §7.2 task 11)."""
    _require_project(session, project_id)
    records = session.scalars(
        select(ContradictionRecord).where(ContradictionRecord.project_id == project_id)
    ).all()
    return [Contradiction.model_validate(r.payload_json) for r in records]


@router.get("/ambiguities", response_model=list[Ambiguity])
def get_ambiguities(project_id: str, session: Session = Depends(get_session)) -> list[Ambiguity]:
    """Retrieve all ambiguities detected for a project (spec §13.1, §7.2 task 12)."""
    _require_project(session, project_id)
    records = session.scalars(
        select(AmbiguityRecord).where(AmbiguityRecord.project_id == project_id)
    ).all()
    return [Ambiguity.model_validate(r.payload_json) for r in records]

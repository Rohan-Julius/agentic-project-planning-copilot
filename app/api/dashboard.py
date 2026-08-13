"""Dashboard endpoint (spec §16.1, §18) — one aggregate row per project."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.schemas.dashboard import DashboardProjectRead
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=list[DashboardProjectRead])
def get_dashboard(session: Session = Depends(get_session)) -> list[DashboardProjectRead]:
    return dashboard_service.get_dashboard(session)

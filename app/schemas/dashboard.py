"""Dashboard aggregate read schema (spec §16.1)."""
from __future__ import annotations

from pydantic import BaseModel


class DashboardProjectRead(BaseModel):
    """One row per project for the project-dashboard screen (spec §16.1).

    Every field is a stored value or a mechanical derivation of one (see
    `app.services.dashboard_service`) — no agent involvement, nothing inferred.
    """

    project_id: str
    name: str
    status: str
    document_count: int
    requirement_analysis_status: str
    clarification_status: str
    planning_status: str
    reviewer_status: str
    approval_status: str

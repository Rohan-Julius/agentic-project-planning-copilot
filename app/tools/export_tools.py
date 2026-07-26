"""Export tools (spec §9.11) — deterministic; never an LLM operation (§8, §20.2).

`export_jira_csv` is the one export operation the spec names as a registered tool. JSON,
Markdown, and ZIP export are produced directly by the export API endpoints
(app/api/export.py) via the same app/services/export_service.py builders — plain
deterministic file generation, not something any agent selects or calls.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.database.session import get_sessionmaker
from app.services.export_service import write_jira_csv_file
from app.tools.validation_tools import load_current_plan


def export_jira_csv(
    project_id: str,
    *,
    session_factory: Callable[[], Session] | sessionmaker | None = None,
    export_dir: Path | None = None,
) -> Path:
    """Write the current plan's Jira CSV to disk and return its path (spec §9.11).
    Raises ValueError if no plan has been generated yet for the project.
    """
    session_factory = session_factory or get_sessionmaker()
    export_dir = export_dir or get_settings().exports_dir

    plan = load_current_plan(project_id, session_factory=session_factory)
    if plan is None:
        raise ValueError(f"No plan generated yet for project {project_id!r}")

    return write_jira_csv_file(project_id, plan, export_dir=export_dir)

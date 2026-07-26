"""export_jira_csv tool tests (Day 14, spec §9.11) — the one export operation the spec
names as a registered agent tool; deterministic, never an LLM call (§8).
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.plan_artifact import PlanArtifactVersion
from app.tools.export_tools import export_jira_csv


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _seed_plan(session_factory) -> None:
    session = session_factory()
    try:
        session.add(
            PlanArtifactVersion(
                version_id="ver_1", project_id="proj_1", version_number=1,
                plan_json={
                    "summary": {"business_problem": "p", "proposed_solution": "s"},
                    "scope": {}, "epics": [], "stories": [], "technical_tasks": [],
                    "raid": {"risks": [], "assumptions": [], "issues": [], "dependencies": []},
                    "traceability": {"rows": []},
                },
                is_current=True,
            )
        )
        session.commit()
    finally:
        session.close()


def test_export_jira_csv_writes_a_file_and_returns_its_path(session_factory, tmp_path):
    _seed_plan(session_factory)

    path = export_jira_csv("proj_1", session_factory=session_factory, export_dir=tmp_path / "exports")

    assert path.exists()
    assert path.name == "jira.csv"
    assert "Issue Type" in path.read_text()


def test_export_jira_csv_raises_for_project_with_no_plan(session_factory, tmp_path):
    with pytest.raises(ValueError, match="No plan generated"):
        export_jira_csv("proj_missing", session_factory=session_factory, export_dir=tmp_path / "exports")

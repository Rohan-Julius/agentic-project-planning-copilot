"""Workflow-event logging tests (Day 7, spec §21)."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.workflow import WorkflowEvent
from app.workflow.events import log_event


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def test_log_event_writes_the_exact_21_field_set(session):
    event = log_event(
        session,
        workflow_run_id="RUN-1",
        project_id="proj_x",
        agent="RequirementAnalyst",
        stage="requirement_analyst",
        action="search_project_documents",
        status="SUCCESS",
        tool="search_project_documents",
        result_count=5,
        duration_ms=420,
    )

    assert event.id is not None
    row = session.scalar(select(WorkflowEvent).where(WorkflowEvent.id == event.id))
    assert row.workflow_run_id == "RUN-1"
    assert row.project_id == "proj_x"
    assert row.agent == "RequirementAnalyst"
    assert row.stage == "requirement_analyst"
    assert row.action == "search_project_documents"
    assert row.tool == "search_project_documents"
    assert row.status == "SUCCESS"
    assert row.result_count == 5
    assert row.duration_ms == 420
    assert row.error is None
    assert row.timestamp is not None


def test_log_event_records_error_status_and_message(session):
    event = log_event(
        session,
        workflow_run_id="RUN-2",
        project_id="proj_x",
        agent="Workflow",
        stage="stop_error",
        action="STOP_WITH_ERROR",
        status="ERROR",
        error="RequirementAnalyst agent is not implemented yet",
    )

    assert event.status == "ERROR"
    assert event.error == "RequirementAnalyst agent is not implemented yet"

"""Regression test (Day 22): WorkflowEvent.duration_ms must be populated on every node's
terminal (SUCCESS/ERROR) log_event call — previously always None (Known-Issues Backlog,
Day 19: every duration reported in the Day 19/20 evaluations had to be reconstructed after
the fact from IN_PROGRESS/SUCCESS timestamp pairs because nothing in app/ ever populated the
field the schema already reserves for it).

Calls supervisor_node directly (not the full compiled graph — no checkpointer/interrupt
machinery needed for this), matching this project's existing pattern of testing a single
node function in isolation with a mocked LLM call.
"""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.workflow import WorkflowEvent
from app.schemas.agents import SupervisorDecision
from app.workflow.graph import supervisor_node


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _base_state(**overrides) -> dict:
    state = {
        "project_id": "proj_x",
        "current_stage": "start",
        "next_action": None,
        "document_ids": [],
        "requirement_ids": [],
        "unresolved_question_ids": [],
        "requirement_analysis_attempts": 0,
        "clarification_approved": False,
        "plan_version_id": None,
        "reviewer_decision": None,
        "reviewer_issue_ids": [],
        "revision_count": 0,
        "final_approved": False,
        "errors": [],
        "workflow_events": [],
    }
    state.update(overrides)
    return state


def _slow_decision(*args, **kwargs) -> SupervisorDecision:
    time.sleep(0.05)
    return SupervisorDecision(
        next_action="RUN_REQUIREMENT_ANALYST", reason="Test", required_inputs=[],
    )


def test_supervisor_node_logs_a_positive_duration_ms(session_factory):
    config = {
        "configurable": {"thread_id": "RUN-duration-test", "session_factory": session_factory},
    }

    with patch("app.agents.supervisor.run_agent", side_effect=_slow_decision):
        supervisor_node(_base_state(), config)

    session = session_factory()
    try:
        event = session.scalar(
            select(WorkflowEvent).where(
                WorkflowEvent.workflow_run_id == "RUN-duration-test",
                WorkflowEvent.action == "RECOMMEND_RUN_REQUIREMENT_ANALYST",
            )
        )
    finally:
        session.close()

    assert event is not None
    assert event.duration_ms is not None
    assert event.duration_ms >= 40  # slept 50ms; generous floor to avoid flakiness

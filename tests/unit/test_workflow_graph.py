"""Graph wiring tests (Day 7) — real compiled graph, real SqliteSaver checkpointer, real
DB session factory. No mocks: proves the node stubs, conditional edges, interrupt/resume,
and loop limits actually work end-to-end, not just the router function in isolation.
"""
from __future__ import annotations

import sqlite3

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from qdrant_client import QdrantClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.project import ProjectRecord
from app.models.workflow import WorkflowEvent
from app.services.vector_service import VectorService
from app.workflow.graph import compile_graph
from app.workflow.routes import NODE_FINAL_GATE


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture
def checkpointer(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "checkpoints.sqlite"), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    return saver


def _base_state(project_id="proj_x", **overrides) -> dict:
    state = {
        "project_id": project_id,
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


def _config(thread_id, session_factory, vector_service=None):
    return {
        "configurable": {
            "thread_id": thread_id,
            "session_factory": session_factory,
            "vector_service": vector_service,
        },
        "recursion_limit": 20,
    }


def test_fresh_run_with_no_documents_terminates_without_infinite_loop(
    session_factory, checkpointer
):
    """Day 9: requirement_analyst is a real agent now (calls live Ollama + Qdrant), not a
    stub. A project with zero uploaded documents should honestly extract nothing (§12.6 —
    never invent) rather than loop forever; §20.1 caps this at one retry (see
    route_next_node's requirement_analysis_attempts check).
    """
    session = session_factory()
    session.add(ProjectRecord(project_id="proj_x", name="Empty Project"))
    session.commit()
    session.close()

    vector_service = VectorService(client=QdrantClient(location=":memory:"))
    graph = compile_graph(checkpointer)
    config = _config("RUN-fresh", session_factory, vector_service)

    result = graph.invoke(_base_state(), config=config)

    # Whatever the live model decides, the run must not still be stuck re-running
    # requirement_analyst indefinitely: either it found requirements and moved on past
    # the node (interrupted at the clarification gate), or it honestly found nothing
    # twice and controlled-stopped.
    assert result.get("requirement_analysis_attempts", 0) <= 2
    if result["requirement_ids"]:
        assert "__interrupt__" in result
    else:
        assert result["current_stage"] == "stop_error"
        assert result["errors"]

    session = session_factory()
    events = session.scalars(
        select(WorkflowEvent).where(WorkflowEvent.workflow_run_id == "RUN-fresh")
    ).all()
    actions = [e.action for e in events]
    assert "EVALUATE_STATE" in actions  # supervisor
    assert "EXTRACT_REQUIREMENTS" in actions  # real requirement_analyst node ran


def test_clarification_gate_interrupts_and_resumes(session_factory, checkpointer):
    graph = compile_graph(checkpointer)
    config = _config("RUN-clarify", session_factory)

    seeded = _base_state(requirement_ids=["REQ-1"], unresolved_question_ids=["CQ-1"])
    result = graph.invoke(seeded, config=config)

    assert "__interrupt__" in result
    assert result["__interrupt__"][0].value["stage"] == "clarification_gate"

    resumed = graph.invoke(Command(resume="approved"), config=config)

    # After resume, clarification_approved is still False in checkpointed state (nothing
    # set it — that's the future clarifications/approve endpoint's job), so the router
    # sends it straight back to the gate; the key assertion is that it did NOT error out
    # or lose the checkpoint, and the RESUMED event was logged.
    assert "__interrupt__" in resumed

    session = session_factory()
    events = session.scalars(
        select(WorkflowEvent).where(WorkflowEvent.workflow_run_id == "RUN-clarify")
    ).all()
    assert any(e.action == "RESUMED" for e in events)


def test_clarification_approve_patch_releases_the_gate(session_factory, checkpointer):
    """Day 10: unlike a bare Command(resume=...) (see the test above, which just
    re-interrupts), patching clarification_approved=True via update_state before resuming
    actually releases the gate — proven by reaching the still-stubbed planning node
    (Day 11 not built yet) and controlled-stopping there.
    """
    graph = compile_graph(checkpointer)
    config = _config("RUN-approve", session_factory)

    seeded = _base_state(requirement_ids=["REQ-1"], unresolved_question_ids=["CQ-1"])
    first = graph.invoke(seeded, config=config)
    assert "__interrupt__" in first
    assert first["__interrupt__"][0].value["stage"] == "clarification_gate"

    graph.update_state(config, {"clarification_approved": True})
    resumed = graph.invoke(Command(resume="approved"), config=config)

    assert "__interrupt__" not in resumed
    assert resumed["current_stage"] == "stop_error"
    assert any("Planning" in e for e in resumed["errors"])


def test_revision_limit_reached_routes_to_final_gate_not_plan_revision(
    session_factory, checkpointer
):
    """§20.1 loop-limit proof at the graph level (not just the router unit test)."""
    graph = compile_graph(checkpointer)
    config = _config("RUN-revision-limit", session_factory)

    seeded = _base_state(
        requirement_ids=["REQ-1"],
        clarification_approved=True,
        plan_version_id="ver_1",
        reviewer_decision="REVISION_REQUIRED",
        revision_count=1,
    )
    result = graph.invoke(seeded, config=config)

    assert "__interrupt__" in result
    assert result["__interrupt__"][0].value["stage"] == NODE_FINAL_GATE


def test_checkpoint_persists_across_a_fresh_connection_and_fresh_compiled_graph(
    session_factory, tmp_path
):
    """DESIGN.md §7.5: interrupts must survive a separate HTTP request/process, not just
    reuse of the same in-memory checkpointer object.
    """
    db_path = str(tmp_path / "separate_process.sqlite")
    thread_id = "RUN-separate-process"

    conn1 = sqlite3.connect(db_path, check_same_thread=False)
    saver1 = SqliteSaver(conn1)
    saver1.setup()
    graph1 = compile_graph(saver1)
    result1 = graph1.invoke(
        _base_state(requirement_ids=["REQ-1"], unresolved_question_ids=["CQ-1"]),
        config=_config(thread_id, session_factory),
    )
    assert "__interrupt__" in result1
    conn1.close()

    # Simulate a brand-new process: new connection, new saver, new compiled graph object.
    conn2 = sqlite3.connect(db_path, check_same_thread=False)
    saver2 = SqliteSaver(conn2)
    graph2 = compile_graph(saver2)
    result2 = graph2.invoke(
        Command(resume="approved"), config=_config(thread_id, session_factory)
    )

    assert "__interrupt__" in result2  # still gated (clarification_approved unset), but resumed cleanly

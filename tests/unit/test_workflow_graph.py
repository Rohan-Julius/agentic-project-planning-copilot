"""Graph wiring tests (Day 7) — real compiled graph, real SqliteSaver checkpointer, real
DB session factory. No mocks: proves the node stubs, conditional edges, interrupt/resume,
and loop limits actually work end-to-end, not just the router function in isolation.
"""
from __future__ import annotations

import sqlite3
from unittest.mock import patch

import httpx
import pytest
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from qdrant_client import QdrantClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.plan_artifact import PlanArtifactVersion
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
    actually releases the gate — proven by reaching the real planning node (Day 13) and
    controlled-stopping there, since state["requirement_ids"] contains a fake "REQ-1" that
    was never actually persisted to the requirements table (this test only seeds workflow
    state, not the DB), so get_requirements() legitimately finds nothing and the Planning
    Agent has no approved requirements to plan from.
    """
    graph = compile_graph(checkpointer)
    config = _config("RUN-approve", session_factory)

    seeded = _base_state(requirement_ids=["REQ-1"], unresolved_question_ids=["CQ-1"])
    first = graph.invoke(seeded, config=config)
    assert "__interrupt__" in first
    assert first["__interrupt__"][0].value["stage"] == "clarification_gate"

    graph.update_state(config, {"clarification_approved": True})
    resumed = graph.invoke(Command(resume="approved"), config=config)

    # Planning is real now: it runs (against zero real requirements — none were persisted
    # to the DB, only faked in workflow state) and does NOT error, so the graph advances
    # past planning to the reviewer, which then runs for real too. Either way the run must
    # not silently vanish: it either interrupts at final_gate (plan produced + reviewed) or
    # controlled-stops with a real error recorded — never loops or crashes uncaught.
    if "__interrupt__" in resumed:
        assert resumed["__interrupt__"][0].value["stage"] in ("final_gate",)
    else:
        assert resumed["current_stage"] == "stop_error"
        assert resumed["errors"]


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


def test_planning_and_reviewer_run_for_real_and_reach_final_gate(session_factory, checkpointer):
    """Checkpoint 3 (§28): with a real approved requirement on record, the graph should run
    planning_node for real, produce a plan_version_id, run reviewer_node for real, and land
    at final_gate — never loop or silently stop with no explanation. Live Ollama + in-memory
    Qdrant, consistent with this file's existing live-agent tests.
    """
    from app.models.requirement import RequirementRecord

    session = session_factory()
    session.add(ProjectRecord(project_id="proj_full", name="Full Cycle Project"))
    session.add(
        RequirementRecord(
            requirement_id="REQ-1", project_id="proj_full", workflow_run_id="RUN-seed",
            title="Card payment", category="functional", classification="SOURCE_BACKED",
            confidence=0.9,
            payload_json={
                "requirement_id": "REQ-1", "title": "Card payment",
                "description": "Customers must be able to pay by card.",
                "category": "functional", "classification": "SOURCE_BACKED", "confidence": 0.9,
                "source_references": [],
            },
        )
    )
    session.commit()
    session.close()

    vector_service = VectorService(client=QdrantClient(location=":memory:"))
    graph = compile_graph(checkpointer)
    config = _config("RUN-full-cycle", session_factory, vector_service)

    seeded = _base_state(
        project_id="proj_full", requirement_ids=["REQ-1"], clarification_approved=True,
    )
    result = graph.invoke(seeded, config=config)

    # plan_version_id must have been set by planning_node; reviewer must have run and
    # produced a decision; the run must end at final_gate (PASS/PASS_WITH_WARNINGS) or, if
    # the model judged REVISION_REQUIRED, either at plan_revision having run once (and then
    # final_gate) or — if something errored — a controlled stop with a recorded error.
    assert result.get("plan_version_id") is not None or result.get("errors")
    if not result.get("errors"):
        assert "__interrupt__" in result
        assert result["__interrupt__"][0].value["stage"] == "final_gate"
        assert result["reviewer_decision"] in ("PASS", "PASS_WITH_WARNINGS", "REVISION_REQUIRED")


def test_revision_cycle_increments_count_and_still_terminates_at_final_gate(
    session_factory, checkpointer
):
    """§20.1: seeding reviewer_decision=REVISION_REQUIRED with revision_count=0 must route
    to plan_revision, run it exactly once (revision_count becomes 1), then — regardless of
    the second reviewer verdict — the run must not exceed the single revision (the router's
    `revision_count < 1` guard, proven at the unit level in test_workflow_routes.py, holds
    end-to-end through the real nodes too).
    """
    from app.models.requirement import RequirementRecord

    session = session_factory()
    session.add(ProjectRecord(project_id="proj_revise", name="Revision Cycle Project"))
    session.add(
        RequirementRecord(
            requirement_id="REQ-1", project_id="proj_revise", workflow_run_id="RUN-seed",
            title="Card payment", category="functional", classification="SOURCE_BACKED",
            confidence=0.9,
            payload_json={
                "requirement_id": "REQ-1", "title": "Card payment",
                "description": "Customers must be able to pay by card.",
                "category": "functional", "classification": "SOURCE_BACKED", "confidence": 0.9,
                "source_references": [],
            },
        )
    )
    session.add(
        PlanArtifactVersion(
            version_id="ver_seed", project_id="proj_revise", version_number=1,
            plan_json={
                "summary": {"business_problem": "p", "proposed_solution": "s"},
                "scope": {}, "epics": [], "stories": [], "technical_tasks": [],
                "raid": {"risks": [], "assumptions": [], "issues": [], "dependencies": []},
                "traceability": {"rows": []},
            },
            is_current=True,
            reviewer_report_json={
                "decision": "REVISION_REQUIRED",
                "missing_requirements": [], "unsupported_claims": [], "duplicate_stories": [],
                "missing_acceptance_criteria": [], "weak_acceptance_criteria": [],
                "traceability_gaps": [], "dependency_issues": [], "warnings": [],
                "revision_instructions": [
                    {
                        "artifact_id": "US-000", "issue_type": "MISSING_ACCEPTANCE_CRITERIA",
                        "description": "No stories were generated.",
                        "recommended_action": "Generate at least one story.",
                    }
                ],
            },
        )
    )
    session.commit()
    session.close()

    vector_service = VectorService(client=QdrantClient(location=":memory:"))
    graph = compile_graph(checkpointer)
    config = _config("RUN-revise-once", session_factory, vector_service)

    seeded = _base_state(
        project_id="proj_revise", requirement_ids=["REQ-1"], clarification_approved=True,
        plan_version_id="ver_seed", reviewer_decision="REVISION_REQUIRED", revision_count=0,
    )
    result = graph.invoke(seeded, config=config)

    assert result.get("errors") or result["revision_count"] == 1
    if not result.get("errors"):
        assert "__interrupt__" in result
        assert result["__interrupt__"][0].value["stage"] == "final_gate"


def test_final_approve_patch_releases_the_gate_and_reaches_export(session_factory, checkpointer):
    """Day 14: mirrors test_clarification_approve_patch_releases_the_gate but for gate 2 —
    patching final_approved=True via update_state (not a bare Command(resume=...)) is what
    actually releases final_gate and reaches the (now real) export node.
    """
    graph = compile_graph(checkpointer)
    config = _config("RUN-final-approve", session_factory)

    seeded = _base_state(
        requirement_ids=["REQ-1"], clarification_approved=True,
        plan_version_id="ver_1", reviewer_decision="PASS",
    )
    first = graph.invoke(seeded, config=config)
    assert "__interrupt__" in first
    assert first["__interrupt__"][0].value["stage"] == NODE_FINAL_GATE

    graph.update_state(config, {"final_approved": True})
    resumed = graph.invoke(Command(resume="approved"), config=config)

    assert "__interrupt__" not in resumed
    assert resumed["current_stage"] == "export"

    session = session_factory()
    events = session.scalars(
        select(WorkflowEvent).where(WorkflowEvent.workflow_run_id == "RUN-final-approve")
    ).all()
    assert any(e.action == "WORKFLOW_COMPLETE" for e in events)


def test_ollama_unreachable_controlled_stops_at_supervisor_not_a_crash(
    session_factory, checkpointer
):
    """§25 'Ollama unavailable': supervisor_node is the graph's first node (START ->
    supervisor). If Ollama is completely down, run_agent() wraps the connection failure in
    AgentError (app/agents/runner.py), supervisor_node catches it and records
    state["errors"], and route_next_node sends the run straight to NODE_STOP_ERROR —
    graph.invoke() must return normally (no exception escapes), proving the whole run
    degrades to a controlled stop instead of crashing the caller.
    """
    session = session_factory()
    session.add(ProjectRecord(project_id="proj_ollama_down", name="Ollama Down Project"))
    session.commit()
    session.close()

    vector_service = VectorService(client=QdrantClient(location=":memory:"))
    graph = compile_graph(checkpointer)
    config = _config("RUN-ollama-down", session_factory, vector_service)

    with patch("ollama.generate", side_effect=httpx.ConnectError("Connection refused")):
        result = graph.invoke(_base_state(project_id="proj_ollama_down"), config=config)

    assert result["current_stage"] == "stop_error"
    assert result["errors"]
    assert any("not reachable" in e for e in result["errors"])

    session = session_factory()
    events = session.scalars(
        select(WorkflowEvent).where(WorkflowEvent.workflow_run_id == "RUN-ollama-down")
    ).all()
    assert any(e.agent == "Supervisor" and e.status == "ERROR" for e in events)


def test_invalid_json_twice_controlled_stops_not_a_crash(session_factory, checkpointer):
    """§25 'LLM returning invalid JSON': same controlled-stop guarantee, but for the other
    AgentError cause — two consecutive schema-invalid responses (app/agents/runner.py's own
    max_retries=1 default), rather than a connection failure.
    """
    session = session_factory()
    session.add(ProjectRecord(project_id="proj_bad_json", name="Bad JSON Project"))
    session.commit()
    session.close()

    vector_service = VectorService(client=QdrantClient(location=":memory:"))
    graph = compile_graph(checkpointer)
    config = _config("RUN-bad-json", session_factory, vector_service)

    with patch("ollama.generate", return_value={"response": "not valid json at all"}):
        result = graph.invoke(_base_state(project_id="proj_bad_json"), config=config)

    assert result["current_stage"] == "stop_error"
    assert result["errors"]
    assert any("Schema validation failed" in e for e in result["errors"])

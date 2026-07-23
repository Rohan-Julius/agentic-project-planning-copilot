"""Unit tests for run_planning_agent_summary_scope_epics (spec §7.3, §13.3-§13.5) — real
function, mocked LLM calls, real (in-memory) DB. Mirrors the testing style of
test_requirement_analyst_agent.py: `run_agent` is mocked at the point of use so the test
exercises real prompt-construction, real requirement/clarification retrieval, and real
deterministic epic-ID assignment without needing a live Ollama.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, ProjectRecord, RequirementRecord
from app.models.requirement import ClarificationQuestionRecord
from app.schemas.common import SourceReference
from app.schemas.planning import EpicDraft, PlanningEpicsResult, PlanningSummaryScopeResult, ProjectSummary, Scope

CITATION = {
    "document_name": "requirements.pdf",
    "page_number": 3,
    "section": "Payments",
    "chunk_id": "DOC-1-CH-003",
}


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        session.add(
            ProjectRecord(
                project_id="PRJ-PLAN",
                name="E-commerce Payments",
                description="Add payment processing to the storefront.",
                methodology="agile_scrum",
            )
        )
        session.add(
            RequirementRecord(
                requirement_id="REQ-1",
                project_id="PRJ-PLAN",
                workflow_run_id="RUN-0",
                title="Card payment",
                category="functional",
                classification="SOURCE_BACKED",
                confidence=0.9,
                payload_json={
                    "requirement_id": "REQ-1",
                    "title": "Card payment",
                    "description": "Customers must be able to pay by card.",
                    "category": "functional",
                    "classification": "SOURCE_BACKED",
                    "confidence": 0.9,
                    "source_references": [CITATION],
                },
            )
        )
        session.add(
            ClarificationQuestionRecord(
                question_id="CQ-1",
                project_id="PRJ-PLAN",
                category="integration",
                priority="High",
                status="ANSWERED",
                payload_json={
                    "question_id": "CQ-1",
                    "category": "integration",
                    "question": "Which payment provider should be used?",
                    "reason_for_asking": "No provider named in the source documents.",
                    "priority": "High",
                    "status": "ANSWERED",
                    "user_answer": "Stripe",
                },
            )
        )
        session.add(
            ClarificationQuestionRecord(
                question_id="CQ-2",
                project_id="PRJ-PLAN",
                category="scope",
                priority="Medium",
                status="PENDING",
                payload_json={
                    "question_id": "CQ-2",
                    "category": "scope",
                    "question": "Should refunds be included in this phase?",
                    "reason_for_asking": "Not mentioned in requirements.",
                    "priority": "Medium",
                    "status": "PENDING",
                    "user_answer": None,
                },
            )
        )
        session.commit()
    return factory


def _summary_scope_result() -> PlanningSummaryScopeResult:
    return PlanningSummaryScopeResult(
        summary=ProjectSummary(
            business_problem="Customers cannot pay by card today.",
            proposed_solution="Integrate Stripe for card payments.",
        ),
        scope=Scope(in_scope=["Card payments via Stripe"]),
    )


def _epics_result() -> PlanningEpicsResult:
    return PlanningEpicsResult(
        epics=[
            EpicDraft(
                title="Card Payments",
                objective="Let customers pay by card",
                business_value="Unlocks online revenue",
                priority="High",
                classification="SOURCE_BACKED",
                source_references=[SourceReference(**CITATION)],
            ),
            EpicDraft(
                title="Payment Notifications",
                objective="Notify customers of payment status",
                business_value="Reduces support load",
                priority="Medium",
                classification="AI_RECOMMENDATION",
            ),
        ]
    )


def test_planning_agent_returns_summary_and_scope(session_factory):
    with patch("app.agents.planning.search_company_standards", return_value=[]), patch(
        "app.agents.planning.run_agent",
        side_effect=[_summary_scope_result(), _epics_result()],
    ):
        from app.agents.planning import run_planning_agent_summary_scope_epics

        summary, scope, _ = run_planning_agent_summary_scope_epics(
            "PRJ-PLAN", "RUN-1", session_factory=session_factory
        )

    assert summary.business_problem == "Customers cannot pay by card today."
    assert scope.in_scope == ["Card payments via Stripe"]


def test_planning_agent_assigns_sequential_epic_ids(session_factory):
    with patch("app.agents.planning.search_company_standards", return_value=[]), patch(
        "app.agents.planning.run_agent",
        side_effect=[_summary_scope_result(), _epics_result()],
    ):
        from app.agents.planning import run_planning_agent_summary_scope_epics

        _, _, epics = run_planning_agent_summary_scope_epics(
            "PRJ-PLAN", "RUN-1", session_factory=session_factory
        )

    assert [e.epic_id for e in epics] == ["EPIC-001", "EPIC-002"]
    assert epics[0].title == "Card Payments"


def test_planning_agent_preserves_citation_from_requirement(session_factory):
    with patch("app.agents.planning.search_company_standards", return_value=[]), patch(
        "app.agents.planning.run_agent",
        side_effect=[_summary_scope_result(), _epics_result()],
    ):
        from app.agents.planning import run_planning_agent_summary_scope_epics

        _, _, epics = run_planning_agent_summary_scope_epics(
            "PRJ-PLAN", "RUN-1", session_factory=session_factory
        )

    source_backed = next(e for e in epics if e.classification == "SOURCE_BACKED")
    assert len(source_backed.source_references) == 1
    ref = source_backed.source_references[0]
    assert ref.chunk_id == CITATION["chunk_id"]
    assert ref.document_name == CITATION["document_name"]
    assert ref.page_number == CITATION["page_number"]
    assert ref.section == CITATION["section"]


def test_planning_agent_prompt_includes_only_answered_clarifications(session_factory):
    with patch("app.agents.planning.search_company_standards", return_value=[]), patch(
        "app.agents.planning.run_agent",
        side_effect=[_summary_scope_result(), _epics_result()],
    ) as mock_run_agent:
        from app.agents.planning import run_planning_agent_summary_scope_epics

        run_planning_agent_summary_scope_epics("PRJ-PLAN", "RUN-1", session_factory=session_factory)

    summary_scope_prompt = mock_run_agent.call_args_list[0].kwargs["prompt"]
    assert "Stripe" in summary_scope_prompt
    assert "Should refunds be included" not in summary_scope_prompt


def test_planning_agent_prompt_forbids_inventing_technology(session_factory):
    with patch("app.agents.planning.search_company_standards", return_value=[]), patch(
        "app.agents.planning.run_agent",
        side_effect=[_summary_scope_result(), _epics_result()],
    ) as mock_run_agent:
        from app.agents.planning import run_planning_agent_summary_scope_epics

        run_planning_agent_summary_scope_epics("PRJ-PLAN", "RUN-1", session_factory=session_factory)

    for call in mock_run_agent.call_args_list:
        prompt = call.kwargs["prompt"].lower()
        assert "technolog" in prompt
        assert "not explicitly named" in prompt


def test_planning_agent_epics_prompt_includes_requirement_evidence(session_factory):
    with patch("app.agents.planning.search_company_standards", return_value=[]), patch(
        "app.agents.planning.run_agent",
        side_effect=[_summary_scope_result(), _epics_result()],
    ) as mock_run_agent:
        from app.agents.planning import run_planning_agent_summary_scope_epics

        run_planning_agent_summary_scope_epics("PRJ-PLAN", "RUN-1", session_factory=session_factory)

    epics_prompt = mock_run_agent.call_args_list[1].kwargs["prompt"]
    assert "Customers must be able to pay by card." in epics_prompt
    assert "REQ-1" in epics_prompt
    assert CITATION["chunk_id"] in epics_prompt

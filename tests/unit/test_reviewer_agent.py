"""Unit tests for run_reviewer_agent (spec §7.4, §13.12) — real function, mocked LLM call,
real (in-memory) DB. Mirrors the testing style of test_planning_agent.py /
test_requirement_analyst_agent.py: `run_agent` is mocked at the point of use so the test
exercises real prompt-construction, real deterministic-validator wiring, and the
structural-failure override without needing a live Ollama.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, DocumentChunkMeta, DocumentRecord, PlanArtifactVersion, ProjectRecord
from app.schemas.common import SourceReference
from app.schemas.planning import (
    AcceptanceCriterion,
    Epic,
    ProjectPlan,
    ProjectSummary,
    RaidLog,
    Scope,
    UserStory,
)
from app.schemas.reviewer import ReviewerIssue, ReviewerReport

CITATION = SourceReference(
    document_name="requirements.pdf", page_number=3, section="Payments", chunk_id="DOC-1-CH-003"
)


def _clean_plan() -> ProjectPlan:
    epic = Epic(
        epic_id="EPIC-001", title="Payments", objective="Let customers pay",
        business_value="Revenue", priority="High", classification="SOURCE_BACKED",
        source_references=[CITATION],
    )
    story = UserStory(
        story_id="US-001", epic_id="EPIC-001", title="Pay by card", persona="Customer",
        story_statement="As a Customer, I want to pay by card, so that I can check out.",
        business_value="Revenue", priority="High",
        acceptance_criteria=[AcceptanceCriterion(criterion_id="AC-001", given="g", when="w", then="t")],
        classification="ASSUMPTION", confidence=0.7,
    )
    return ProjectPlan(
        summary=ProjectSummary(business_problem="p", proposed_solution="s"),
        scope=Scope(), epics=[epic], stories=[story], raid=RaidLog(),
    )


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    return factory


def _seed_plan(session_factory, project_id: str, plan: ProjectPlan) -> None:
    """Seeds the project + plan version, plus a DocumentChunkMeta row for CITATION so a
    SOURCE_BACKED item citing it is NOT flagged as a dangling citation by
    validate_project_plan — callers that want a dangling citation use a different chunk_id.
    """
    with session_factory() as session:
        session.add(ProjectRecord(project_id=project_id, name="Review Project"))
        session.add(
            DocumentRecord(
                document_id=f"doc_{project_id}", project_id=project_id,
                document_name="requirements.pdf", file_path="/tmp/requirements.pdf",
            )
        )
        session.add(
            DocumentChunkMeta(
                chunk_id=CITATION.chunk_id, document_id=f"doc_{project_id}", project_id=project_id,
                page_number=CITATION.page_number, section=CITATION.section or "",
            )
        )
        session.add(
            PlanArtifactVersion(
                version_id="ver_1", project_id=project_id, version_number=1,
                plan_json=plan.model_dump(mode="json"), is_current=True,
            )
        )
        session.commit()


def test_run_reviewer_agent_raises_when_no_plan_exists(session_factory):
    from app.agents.reviewer import run_reviewer_agent

    with session_factory() as session:
        session.add(ProjectRecord(project_id="PRJ-EMPTY", name="Empty"))
        session.commit()

    with pytest.raises(ValueError, match="No plan generated"):
        run_reviewer_agent("PRJ-EMPTY", "RUN-1", session_factory=session_factory)


def test_run_reviewer_agent_returns_llm_decision_when_validator_passes(session_factory):
    from app.agents.reviewer import run_reviewer_agent

    _seed_plan(session_factory, "PRJ-R1", _clean_plan())
    llm_report = ReviewerReport(decision="PASS_WITH_WARNINGS", warnings=["Story could be split."])

    with patch("app.agents.reviewer.run_agent", return_value=llm_report):
        report = run_reviewer_agent("PRJ-R1", "RUN-1", session_factory=session_factory)

    assert report.decision == "PASS_WITH_WARNINGS"
    assert report.warnings == ["Story could be split."]


def test_run_reviewer_agent_forces_revision_on_structural_failure(session_factory):
    """Even if the LLM says PASS, a dangling citation (Python-detected) must force
    REVISION_REQUIRED — structural correctness is never left to agent judgement alone.
    """
    from app.agents.reviewer import run_reviewer_agent

    dangling_epic = Epic(
        epic_id="EPIC-001", title="Payments", objective="Let customers pay",
        business_value="Revenue", priority="High", classification="SOURCE_BACKED",
        source_references=[SourceReference(document_name="ghost.pdf", chunk_id="NOPE")],
    )
    plan = ProjectPlan(
        summary=ProjectSummary(business_problem="p", proposed_solution="s"), scope=Scope(),
        epics=[dangling_epic],
        stories=[
            UserStory(
                story_id="US-001", epic_id="EPIC-001", title="t", persona="p",
                story_statement="As a Customer, I want x, so that y.", business_value="v",
                priority="High",
                acceptance_criteria=[AcceptanceCriterion(criterion_id="AC-001", given="g", when="w", then="t")],
                classification="ASSUMPTION", confidence=0.7,
            )
        ],
        raid=RaidLog(),
    )
    _seed_plan(session_factory, "PRJ-R2", plan)
    llm_report = ReviewerReport(decision="PASS")  # LLM wrongly thinks it's fine

    with patch("app.agents.reviewer.run_agent", return_value=llm_report):
        report = run_reviewer_agent("PRJ-R2", "RUN-1", session_factory=session_factory)

    assert report.decision == "REVISION_REQUIRED"
    assert any(i.issue_type == "DANGLING_CITATION" for i in report.revision_instructions)


def test_run_reviewer_agent_does_not_duplicate_findings_when_plan_is_structurally_clean(session_factory):
    """When the validator finds nothing wrong, the LLM's own REVISION_REQUIRED report passes
    through untouched — no forced issues to append."""
    from app.agents.reviewer import run_reviewer_agent

    _seed_plan(session_factory, "PRJ-R3", _clean_plan())
    llm_report = ReviewerReport(
        decision="REVISION_REQUIRED",
        revision_instructions=[
            ReviewerIssue(artifact_id="US-001", issue_type="WEAK_AC", description="d", recommended_action="a")
        ],
    )

    with patch("app.agents.reviewer.run_agent", return_value=llm_report):
        report = run_reviewer_agent("PRJ-R3", "RUN-1", session_factory=session_factory)

    assert report.decision == "REVISION_REQUIRED"
    assert len(report.revision_instructions) == 1  # not duplicated with validator findings


def test_run_reviewer_agent_still_surfaces_structural_errors_when_llm_already_says_revision_required(
    session_factory,
):
    """Found live: when the LLM's own decision already happens to be REVISION_REQUIRED (for
    unrelated reasons), the deterministic validator's own findings (e.g. dangling citations)
    were previously silently dropped instead of appended — a structurally invalid plan could
    reach final approval with the human never having seen the actual validator error, only
    whatever unrelated issue the LLM separately raised.
    """
    from app.agents.reviewer import run_reviewer_agent

    dangling_epic = Epic(
        epic_id="EPIC-001", title="Payments", objective="Let customers pay",
        business_value="Revenue", priority="High", classification="SOURCE_BACKED",
        source_references=[SourceReference(document_name="ghost.pdf", chunk_id="NOPE")],
    )
    plan = ProjectPlan(
        summary=ProjectSummary(business_problem="p", proposed_solution="s"), scope=Scope(),
        epics=[dangling_epic],
        stories=[
            UserStory(
                story_id="US-001", epic_id="EPIC-001", title="t", persona="p",
                story_statement="As a Customer, I want x, so that y.", business_value="v",
                priority="High",
                acceptance_criteria=[AcceptanceCriterion(criterion_id="AC-001", given="g", when="w", then="t")],
                classification="ASSUMPTION", confidence=0.7,
            )
        ],
        raid=RaidLog(),
    )
    _seed_plan(session_factory, "PRJ-R4", plan)
    llm_report = ReviewerReport(
        decision="REVISION_REQUIRED",
        revision_instructions=[
            ReviewerIssue(artifact_id="US-001", issue_type="WEAK_AC", description="d", recommended_action="a")
        ],
    )

    with patch("app.agents.reviewer.run_agent", return_value=llm_report):
        report = run_reviewer_agent("PRJ-R4", "RUN-1", session_factory=session_factory)

    assert report.decision == "REVISION_REQUIRED"
    issue_types = {i.issue_type for i in report.revision_instructions}
    assert "WEAK_AC" in issue_types  # the LLM's own finding is preserved
    assert "DANGLING_CITATION" in issue_types  # and the validator's finding is no longer dropped


def test_run_reviewer_agent_prompt_includes_requirements_and_plan_content(session_factory):
    from app.agents.reviewer import run_reviewer_agent

    with session_factory() as session:
        from app.models import RequirementRecord

        session.add(ProjectRecord(project_id="PRJ-R4", name="Review Project"))
        session.add(
            RequirementRecord(
                requirement_id="REQ-1", project_id="PRJ-R4", workflow_run_id="RUN-0",
                title="Card payment", category="functional", classification="SOURCE_BACKED",
                confidence=0.9,
                payload_json={
                    "requirement_id": "REQ-1", "title": "Card payment",
                    "description": "Customers must pay by card.", "category": "functional",
                    "classification": "SOURCE_BACKED", "confidence": 0.9,
                    "source_references": [CITATION.model_dump()],
                },
            )
        )
        session.add(
            PlanArtifactVersion(
                version_id="ver_1", project_id="PRJ-R4", version_number=1,
                plan_json=_clean_plan().model_dump(mode="json"), is_current=True,
            )
        )
        session.commit()

    llm_report = ReviewerReport(decision="PASS")
    with patch("app.agents.reviewer.run_agent", return_value=llm_report) as mock_run_agent:
        run_reviewer_agent("PRJ-R4", "RUN-1", session_factory=session_factory)

    prompt = mock_run_agent.call_args.kwargs["prompt"]
    assert "REQ-1" in prompt
    assert "EPIC-001" in prompt
    assert "US-001" in prompt

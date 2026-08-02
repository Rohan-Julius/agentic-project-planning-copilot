"""Tests for the deterministic plan validator and traceability checker (spec §9.8, §9.9,
DESIGN.md §10). Real (in-memory) DB, no LLM involved — these tools are pure Python.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, DocumentChunkMeta, DocumentRecord, PlanArtifactVersion, ProjectRecord
from app.schemas.common import SourceReference
from app.schemas.planning import (
    AcceptanceCriterion,
    Dependency,
    Epic,
    ProjectPlan,
    ProjectSummary,
    RaidLog,
    Scope,
    UserStory,
)
from app.tools.validation_tools import check_traceability, validate_project_plan

CITATION = SourceReference(
    document_name="requirements.pdf", page_number=3, section="Payments", chunk_id="DOC-1-CH-003"
)


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        session.add(ProjectRecord(project_id="PRJ-V", name="Validation Project"))
        session.add(
            DocumentRecord(
                document_id="doc_1", project_id="PRJ-V", document_name="requirements.pdf",
                file_path="/tmp/requirements.pdf",
            )
        )
        session.add(
            DocumentChunkMeta(
                chunk_id="DOC-1-CH-003", document_id="doc_1", project_id="PRJ-V",
                page_number=3, section="Payments",
            )
        )
        session.commit()
    return factory


def _minimal_plan(**overrides) -> ProjectPlan:
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
    defaults = dict(
        summary=ProjectSummary(business_problem="p", proposed_solution="s"),
        scope=Scope(),
        epics=[epic],
        stories=[story],
        technical_tasks=[],
        raid=RaidLog(),
    )
    defaults.update(overrides)
    return ProjectPlan(**defaults)


def _save_plan(session_factory, project_id: str, plan: ProjectPlan) -> None:
    with session_factory() as session:
        session.add(
            PlanArtifactVersion(
                version_id="ver_1", project_id=project_id, version_number=1,
                plan_json=plan.model_dump(mode="json"), is_current=True,
            )
        )
        session.commit()


def test_validate_project_plan_no_plan_returns_invalid(session_factory):
    result = validate_project_plan("PRJ-V", session_factory=session_factory)
    assert result.is_valid is False
    assert result.errors[0].code == "NO_PLAN"


def test_validate_project_plan_detects_malformed_plan_json(session_factory):
    """A plan_json blob that isn't even a valid ProjectPlan shape (e.g. hand-edited or
    corrupted) must be caught by validate_project_plan's own try/except around
    ProjectPlan.model_validate — not raise an uncaught exception. Spec §9.8 "schema
    validity" had zero test coverage before this.
    """
    with session_factory() as session:
        session.add(
            PlanArtifactVersion(
                version_id="ver_bad", project_id="PRJ-V", version_number=1,
                plan_json={"summary": "not even an object with the right shape"},
                is_current=True,
            )
        )
        session.commit()

    result = validate_project_plan("PRJ-V", session_factory=session_factory)

    assert result.is_valid is False
    assert result.errors[0].code == "SCHEMA_INVALID"


def test_validate_project_plan_accepts_a_clean_plan(session_factory):
    _save_plan(session_factory, "PRJ-V", _minimal_plan())
    result = validate_project_plan("PRJ-V", session_factory=session_factory)
    assert result.is_valid is True
    assert result.errors == []


def test_validate_project_plan_detects_epic_with_blank_title(session_factory):
    """Epic.title/objective have no Pydantic min_length (app/schemas/planning.py) — a
    whitespace-only title passes construction silently. _check_missing_mandatory_fields
    exists specifically to catch this (spec §9.8 "missing mandatory fields") and, per the
    Day-16 gap audit, had zero test coverage anywhere in the suite.
    """
    blank_epic = Epic(
        epic_id="EPIC-001", title="   ", objective="Let customers pay",
        business_value="Revenue", priority="High", classification="ASSUMPTION",
    )
    plan = _minimal_plan(epics=[blank_epic])
    _save_plan(session_factory, "PRJ-V", plan)

    result = validate_project_plan("PRJ-V", session_factory=session_factory)

    assert result.is_valid is False
    assert any(
        e.code == "MISSING_MANDATORY_FIELD" and e.artifact_id == "EPIC-001" for e in result.errors
    )


def test_validate_project_plan_detects_story_with_blank_story_statement(session_factory):
    blank_story = UserStory(
        story_id="US-001", epic_id="EPIC-001", title="Pay by card", persona="Customer",
        story_statement="   ", business_value="Revenue", priority="High",
        acceptance_criteria=[AcceptanceCriterion(criterion_id="AC-001", given="g", when="w", then="t")],
        classification="ASSUMPTION", confidence=0.7,
    )
    plan = _minimal_plan(stories=[blank_story])
    _save_plan(session_factory, "PRJ-V", plan)

    result = validate_project_plan("PRJ-V", session_factory=session_factory)

    assert result.is_valid is False
    assert any(
        e.code == "MISSING_MANDATORY_FIELD" and e.artifact_id == "US-001" for e in result.errors
    )


def test_validate_project_plan_detects_dangling_citation(session_factory):
    bad_epic = Epic(
        epic_id="EPIC-001", title="Payments", objective="Let customers pay",
        business_value="Revenue", priority="High", classification="SOURCE_BACKED",
        source_references=[SourceReference(document_name="ghost.pdf", chunk_id="DOES-NOT-EXIST")],
    )
    plan = _minimal_plan(epics=[bad_epic])
    _save_plan(session_factory, "PRJ-V", plan)

    result = validate_project_plan("PRJ-V", session_factory=session_factory)

    assert result.is_valid is False
    assert any(e.code == "DANGLING_CITATION" for e in result.errors)


def test_validate_project_plan_detects_circular_dependency(session_factory):
    raid = RaidLog(
        dependencies=[
            Dependency(dependency_id="DEP-001", blocking_item_id="EPIC-001", blocked_item_id="US-001",
                       dependency_type="BLOCKS"),
            Dependency(dependency_id="DEP-002", blocking_item_id="US-001", blocked_item_id="EPIC-001",
                       dependency_type="BLOCKS"),
        ]
    )
    plan = _minimal_plan(raid=raid)
    _save_plan(session_factory, "PRJ-V", plan)

    result = validate_project_plan("PRJ-V", session_factory=session_factory)

    assert result.is_valid is False
    assert any(e.code == "CIRCULAR_DEPENDENCY" for e in result.errors)


def test_validate_project_plan_detects_self_loop_dependency(session_factory):
    plan = _minimal_plan(
        raid=RaidLog(
            dependencies=[
                Dependency(dependency_id="DEP-001", blocking_item_id="EPIC-001",
                           blocked_item_id="EPIC-001", dependency_type="BLOCKS"),
            ]
        )
    )
    _save_plan(session_factory, "PRJ-V", plan)

    result = validate_project_plan("PRJ-V", session_factory=session_factory)

    assert result.is_valid is False
    assert any(e.code == "CIRCULAR_DEPENDENCY" for e in result.errors)


def test_validate_project_plan_detects_three_node_cycle_among_valid_edges(session_factory):
    story_2 = UserStory(
        story_id="US-002", epic_id="EPIC-001", title="Refund", persona="Customer",
        story_statement="As a Customer, I want a refund, so that I get my money back.",
        business_value="Trust",
        priority="High",
        acceptance_criteria=[AcceptanceCriterion(criterion_id="AC-002", given="g", when="w", then="t")],
        classification="ASSUMPTION", confidence=0.6,
    )
    plan = _minimal_plan(
        stories=[story_2],
        raid=RaidLog(
            dependencies=[
                # EPIC-001 -> US-001 -> US-002 -> EPIC-001: a 3-node cycle, plus one
                # non-cyclic valid edge (EPIC-001 -> US-002) mixed in to prove the cycle
                # detector doesn't just flag the first edge it sees. (US-001 isn't in this
                # plan's stories list, so DEP-001/DEP-002 also legitimately trip
                # INVALID_PARENT_REF alongside CIRCULAR_DEPENDENCY — both are expected.)
                Dependency(dependency_id="DEP-001", blocking_item_id="EPIC-001",
                           blocked_item_id="US-001", dependency_type="BLOCKS"),
                Dependency(dependency_id="DEP-002", blocking_item_id="US-001",
                           blocked_item_id="US-002", dependency_type="BLOCKS"),
                Dependency(dependency_id="DEP-003", blocking_item_id="US-002",
                           blocked_item_id="EPIC-001", dependency_type="BLOCKS"),
                Dependency(dependency_id="DEP-004", blocking_item_id="EPIC-001",
                           blocked_item_id="US-002", dependency_type="RELATES_TO"),
            ]
        ),
    )
    _save_plan(session_factory, "PRJ-V", plan)

    result = validate_project_plan("PRJ-V", session_factory=session_factory)

    assert result.is_valid is False
    assert any(e.code == "CIRCULAR_DEPENDENCY" for e in result.errors)


def test_validate_project_plan_detects_duplicate_task_id(session_factory):
    from app.schemas.planning import TechnicalTask

    plan = _minimal_plan(
        technical_tasks=[
            TechnicalTask(task_id="TASK-001", category="Backend", description="a"),
            TechnicalTask(task_id="TASK-001", category="Frontend", description="b"),
        ]
    )
    _save_plan(session_factory, "PRJ-V", plan)

    result = validate_project_plan("PRJ-V", session_factory=session_factory)

    assert result.is_valid is False
    assert any(e.code == "DUPLICATE_ID" and e.artifact_id == "TASK-001" for e in result.errors)


def test_validate_project_plan_detects_duplicate_dependency_id(session_factory):
    plan = _minimal_plan(
        raid=RaidLog(
            dependencies=[
                Dependency(dependency_id="DEP-001", blocking_item_id="EPIC-001",
                           blocked_item_id="US-001", dependency_type="BLOCKS"),
                Dependency(dependency_id="DEP-001", blocking_item_id="US-001",
                           blocked_item_id="EPIC-001", dependency_type="RELATES_TO"),
            ]
        )
    )
    _save_plan(session_factory, "PRJ-V", plan)

    result = validate_project_plan("PRJ-V", session_factory=session_factory)

    assert result.is_valid is False
    assert any(e.code == "DUPLICATE_ID" and e.artifact_id == "DEP-001" for e in result.errors)


def test_validate_project_plan_detects_duplicate_risk_id(session_factory):
    from app.schemas.planning import Risk

    plan = _minimal_plan(
        raid=RaidLog(
            risks=[
                Risk(risk_id="RISK-001", description="a", probability="Low", impact="Low",
                     severity="Low", mitigation="m", contingency="c", classification="ASSUMPTION"),
                Risk(risk_id="RISK-001", description="b", probability="High", impact="High",
                     severity="High", mitigation="m2", contingency="c2", classification="ASSUMPTION"),
            ]
        )
    )
    _save_plan(session_factory, "PRJ-V", plan)

    result = validate_project_plan("PRJ-V", session_factory=session_factory)

    assert result.is_valid is False
    assert any(e.code == "DUPLICATE_ID" and e.artifact_id == "RISK-001" for e in result.errors)


def test_validate_project_plan_detects_duplicate_assumption_id(session_factory):
    from app.schemas.planning import Assumption

    plan = _minimal_plan(
        raid=RaidLog(
            assumptions=[
                Assumption(assumption_id="ASSUMP-001", description="a", classification="ASSUMPTION"),
                Assumption(assumption_id="ASSUMP-001", description="b", classification="ASSUMPTION"),
            ]
        )
    )
    _save_plan(session_factory, "PRJ-V", plan)

    result = validate_project_plan("PRJ-V", session_factory=session_factory)

    assert result.is_valid is False
    assert any(e.code == "DUPLICATE_ID" and e.artifact_id == "ASSUMP-001" for e in result.errors)


def test_validate_project_plan_detects_duplicate_issue_id(session_factory):
    from app.schemas.planning import Issue

    plan = _minimal_plan(
        raid=RaidLog(
            issues=[
                Issue(issue_id="ISSUE-001", description="a"),
                Issue(issue_id="ISSUE-001", description="b"),
            ]
        )
    )
    _save_plan(session_factory, "PRJ-V", plan)

    result = validate_project_plan("PRJ-V", session_factory=session_factory)

    assert result.is_valid is False
    assert any(e.code == "DUPLICATE_ID" and e.artifact_id == "ISSUE-001" for e in result.errors)


def test_validate_project_plan_detects_duplicate_acceptance_criterion_id(session_factory):
    story = UserStory(
        story_id="US-002", epic_id="EPIC-001", title="Refund", persona="Customer",
        story_statement="As a Customer, I want a refund, so that I get my money back.",
        business_value="Trust",
        priority="High",
        acceptance_criteria=[
            AcceptanceCriterion(criterion_id="AC-001", given="g1", when="w1", then="t1"),
            AcceptanceCriterion(criterion_id="AC-001", given="g2", when="w2", then="t2"),
        ],
        classification="ASSUMPTION", confidence=0.6,
    )
    plan = _minimal_plan(stories=[story])
    _save_plan(session_factory, "PRJ-V", plan)

    result = validate_project_plan("PRJ-V", session_factory=session_factory)

    assert result.is_valid is False
    assert any(e.code == "DUPLICATE_ID" and e.artifact_id == "AC-001" for e in result.errors)


def test_validate_project_plan_detects_invalid_parent_reference(session_factory):
    from app.schemas.planning import TechnicalTask

    plan = _minimal_plan(
        technical_tasks=[TechnicalTask(task_id="TASK-001", story_id="US-999", category="Backend", description="a")]
    )
    _save_plan(session_factory, "PRJ-V", plan)

    result = validate_project_plan("PRJ-V", session_factory=session_factory)

    assert result.is_valid is False
    assert any(e.code == "INVALID_PARENT_REF" for e in result.errors)


def test_validate_project_plan_detects_invalid_dependency_blocking_endpoint(session_factory):
    plan = _minimal_plan(
        raid=RaidLog(
            dependencies=[
                Dependency(dependency_id="DEP-001", blocking_item_id="EPIC-999",
                           blocked_item_id="US-001", dependency_type="BLOCKS"),
            ]
        )
    )
    _save_plan(session_factory, "PRJ-V", plan)

    result = validate_project_plan("PRJ-V", session_factory=session_factory)

    assert result.is_valid is False
    assert any(
        e.code == "INVALID_PARENT_REF" and "EPIC-999" in e.message for e in result.errors
    )


def test_validate_project_plan_detects_invalid_dependency_blocked_endpoint(session_factory):
    plan = _minimal_plan(
        raid=RaidLog(
            dependencies=[
                Dependency(dependency_id="DEP-001", blocking_item_id="EPIC-001",
                           blocked_item_id="US-999", dependency_type="BLOCKS"),
            ]
        )
    )
    _save_plan(session_factory, "PRJ-V", plan)

    result = validate_project_plan("PRJ-V", session_factory=session_factory)

    assert result.is_valid is False
    assert any(
        e.code == "INVALID_PARENT_REF" and "US-999" in e.message for e in result.errors
    )


# --- Defense-in-depth checks unreachable via the public API ---------------------------
#
# _check_stories_structure (STORY_WITHOUT_EPIC, MISSING_ACCEPTANCE_CRITERIA) and half of
# _check_source_references (the "SOURCE_BACKED with zero source_references" branch) exist as
# defense-in-depth against a hand-edited plan_json row (see _check_stories_structure's own
# docstring). But as currently wired they are unreachable through the public
# validate_project_plan(): UserStory.epic_id and .acceptance_criteria both have
# Field(min_length=1), ProjectPlan's own cross-reference validator rejects an unknown
# epic_id, and GroundedMixin's own validator guarantees a SOURCE_BACKED item can't have empty
# source_references — all of which fire *inside* ProjectPlan.model_validate(), before these
# functions ever run, surfacing as SCHEMA_INVALID instead. The tests below (a) exercise the
# private functions directly via .model_construct() (bypasses validation) to prove their own
# logic is correct in isolation — a regression guard if the schema is ever relaxed the way
# EpicDraft/UserStoryDraft already were this session — and (b) document what the public API
# actually does today with equivalent input.


def test_check_stories_structure_detects_story_without_valid_epic_directly():
    from app.tools.validation_tools import _check_stories_structure

    bad_story = UserStory.model_construct(
        story_id="US-001", epic_id="EPIC-DOES-NOT-EXIST", title="t", persona="p",
        story_statement="s", business_value="v", priority="High",
        acceptance_criteria=[AcceptanceCriterion(criterion_id="AC-001", given="g", when="w", then="t")],
        dependencies=[], assumptions=[], suggested_story_points=None, confidence=0.5,
        classification="ASSUMPTION", source_references=[],
    )
    plan = ProjectPlan.model_construct(
        summary=ProjectSummary(business_problem="p", proposed_solution="s"), scope=Scope(),
        epics=[], stories=[bad_story], technical_tasks=[], raid=RaidLog(),
        sprint_plan=None, traceability=None,
    )

    errors = _check_stories_structure(plan)

    assert any(e.code == "STORY_WITHOUT_EPIC" and e.artifact_id == "US-001" for e in errors)


def test_check_stories_structure_detects_story_without_acceptance_criteria_directly():
    from app.tools.validation_tools import _check_stories_structure

    bad_story = UserStory.model_construct(
        story_id="US-001", epic_id="EPIC-001", title="t", persona="p",
        story_statement="s", business_value="v", priority="High",
        acceptance_criteria=[], dependencies=[], assumptions=[],
        suggested_story_points=None, confidence=0.5,
        classification="ASSUMPTION", source_references=[],
    )
    epic = Epic(
        epic_id="EPIC-001", title="t", objective="o", business_value="v",
        priority="High", classification="ASSUMPTION",
    )
    plan = ProjectPlan.model_construct(
        summary=ProjectSummary(business_problem="p", proposed_solution="s"), scope=Scope(),
        epics=[epic], stories=[bad_story], technical_tasks=[], raid=RaidLog(),
        sprint_plan=None, traceability=None,
    )

    errors = _check_stories_structure(plan)

    assert any(e.code == "MISSING_ACCEPTANCE_CRITERIA" and e.artifact_id == "US-001" for e in errors)


def test_check_source_references_detects_source_backed_item_with_no_citation_directly(session_factory):
    from app.tools.validation_tools import _check_source_references

    bad_epic = Epic.model_construct(
        epic_id="EPIC-001", title="t", objective="o", business_value="v",
        priority="High", dependencies=[], risks=[], grounding_requirement_ids=[],
        classification="SOURCE_BACKED", source_references=[],
    )
    plan = ProjectPlan.model_construct(
        summary=ProjectSummary(business_problem="p", proposed_solution="s"), scope=Scope(),
        epics=[bad_epic], stories=[], technical_tasks=[], raid=RaidLog(),
        sprint_plan=None, traceability=None,
    )

    with session_factory() as session:
        errors = _check_source_references(plan, "PRJ-V", session)

    assert any(e.code == "MISSING_SOURCE_REFERENCE" and e.artifact_id == "EPIC-001" for e in errors)


def test_validate_project_plan_reports_schema_invalid_not_story_without_epic(session_factory):
    """Documents current real behavior: the SAME bad shape as
    test_check_stories_structure_detects_story_without_valid_epic_directly, saved and loaded
    through the actual public API, surfaces as SCHEMA_INVALID (via ProjectPlan's own
    cross-reference validator) — never reaching _check_stories_structure at all. If this
    test ever starts failing because STORY_WITHOUT_EPIC appears instead, that means a schema
    change made the dedicated check reachable again — update this test's assertion, don't
    just delete it.
    """
    with session_factory() as session:
        session.add(
            PlanArtifactVersion(
                version_id="ver_bad", project_id="PRJ-V", version_number=1,
                plan_json={
                    "summary": {"business_problem": "p", "proposed_solution": "s"},
                    "scope": {},
                    "epics": [],
                    "stories": [{
                        "story_id": "US-001", "epic_id": "EPIC-DOES-NOT-EXIST",
                        "title": "t", "persona": "p", "story_statement": "s",
                        "business_value": "v", "priority": "High",
                        "acceptance_criteria": [
                            {"criterion_id": "AC-001", "given": "g", "when": "w", "then": "t"}
                        ],
                        "classification": "ASSUMPTION", "confidence": 0.5,
                    }],
                    "technical_tasks": [], "raid": {},
                },
                is_current=True,
            )
        )
        session.commit()

    result = validate_project_plan("PRJ-V", session_factory=session_factory)

    assert result.is_valid is False
    assert result.errors[0].code == "SCHEMA_INVALID"
    assert not any(e.code == "STORY_WITHOUT_EPIC" for e in result.errors)


def test_check_traceability_no_plan_returns_empty_result(session_factory):
    result = check_traceability("PRJ-V", session_factory=session_factory)
    assert result.matrix.rows == []
    assert result.coverage_gaps == []


def test_check_traceability_reports_coverage_gap_for_untraced_requirement(session_factory):
    from app.schemas.planning import TraceabilityMatrix, TraceabilityRow

    plan = _minimal_plan(
        traceability=TraceabilityMatrix(
            rows=[TraceabilityRow(requirement_id="REQ-1", source_references=[CITATION], epic_id=None)]
        )
    )
    _save_plan(session_factory, "PRJ-V", plan)

    result = check_traceability("PRJ-V", session_factory=session_factory)

    assert result.coverage_gaps == ["REQ-1"]


def test_check_traceability_reports_orphan_story(session_factory):
    plan = _minimal_plan()  # US-001 exists but plan.traceability defaults to empty rows
    _save_plan(session_factory, "PRJ-V", plan)

    result = check_traceability("PRJ-V", session_factory=session_factory)

    assert "US-001" in result.orphan_story_ids

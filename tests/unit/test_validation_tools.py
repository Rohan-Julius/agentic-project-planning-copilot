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


def test_validate_project_plan_accepts_a_clean_plan(session_factory):
    _save_plan(session_factory, "PRJ-V", _minimal_plan())
    result = validate_project_plan("PRJ-V", session_factory=session_factory)
    assert result.is_valid is True
    assert result.errors == []


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


def test_validate_project_plan_detects_invalid_parent_reference(session_factory):
    from app.schemas.planning import TechnicalTask

    plan = _minimal_plan(
        technical_tasks=[TechnicalTask(task_id="TASK-001", story_id="US-999", category="Backend", description="a")]
    )
    _save_plan(session_factory, "PRJ-V", plan)

    result = validate_project_plan("PRJ-V", session_factory=session_factory)

    assert result.is_valid is False
    assert any(e.code == "INVALID_PARENT_REF" for e in result.errors)


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

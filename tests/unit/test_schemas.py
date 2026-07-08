"""Day 2 schema tests: validation, citation-presence grounding rule, epic/story parent rule.

Covers spec §25 "Pydantic schemas" and "story-parent validation" unit test requirements,
plus the project's strict-grounding rule (see docs/ARCHITECTURE.md §5a).
"""
import pytest
from pydantic import ValidationError

from app.schemas import (
    AcceptanceCriterion,
    Epic,
    ProjectPlan,
    ProjectSummary,
    Requirement,
    Scope,
    SourceReference,
    SprintPlan,
    SupervisorDecision,
    UserStory,
)

SOURCE = SourceReference(
    document_name="requirements.pdf", page_number=5, section="Payments", chunk_id="DOC-1-CH-1"
)


def _epic(epic_id: str = "EPIC-1") -> Epic:
    return Epic(
        epic_id=epic_id,
        title="Payments",
        objective="Enable payments",
        business_value="Revenue",
        priority="High",
        classification="SOURCE_BACKED",
        source_references=[SOURCE],
    )


def _story(story_id: str = "US-1", epic_id: str = "EPIC-1") -> UserStory:
    return UserStory(
        story_id=story_id,
        epic_id=epic_id,
        title="Pay by card",
        persona="Customer",
        story_statement="As a customer, I want to pay by card, so that I can complete checkout.",
        business_value="Enables revenue",
        priority="High",
        acceptance_criteria=[AcceptanceCriterion(criterion_id="AC-1", given="cart", when="pay", then="charged")],
        confidence=0.8,
        classification="SOURCE_BACKED",
        source_references=[SOURCE],
    )


# --- Basic schema validation (valid + invalid fixtures) ---

def test_supervisor_decision_valid():
    decision = SupervisorDecision(next_action="RUN_PLANNING_AGENT", reason="requirements clear")
    assert decision.next_action == "RUN_PLANNING_AGENT"


def test_supervisor_decision_rejects_unknown_action():
    with pytest.raises(ValidationError):
        SupervisorDecision(next_action="DO_SOMETHING_ELSE", reason="nope")


def test_requirement_valid_source_backed():
    req = Requirement(
        requirement_id="REQ-1",
        title="Login",
        description="Users can log in",
        category="functional",
        classification="SOURCE_BACKED",
        source_references=[SOURCE],
        confidence=0.9,
    )
    assert req.category == "functional"


def test_requirement_rejects_bad_confidence():
    with pytest.raises(ValidationError):
        Requirement(
            requirement_id="REQ-1",
            title="Login",
            description="Users can log in",
            category="functional",
            classification="ASSUMPTION",
            confidence=1.5,  # out of [0,1]
        )


# --- Grounding / citation-presence rule (project strict rule, docs/ARCHITECTURE.md §5a) ---

def test_source_backed_requirement_without_citation_rejected():
    with pytest.raises(ValidationError, match="SOURCE_BACKED requires at least one source_reference"):
        Requirement(
            requirement_id="REQ-2",
            title="Fast",
            description="The app should be fast",
            category="non_functional",
            classification="SOURCE_BACKED",
            source_references=[],
            confidence=0.5,
        )


def test_assumption_classification_does_not_require_citation():
    req = Requirement(
        requirement_id="REQ-3",
        title="Guess",
        description="Assume single currency",
        category="business_rule",
        classification="ASSUMPTION",
        source_references=[],
        confidence=0.4,
    )
    assert req.source_references == []


def test_epic_source_backed_without_citation_rejected():
    with pytest.raises(ValidationError):
        Epic(
            epic_id="EPIC-2",
            title="Payments",
            objective="x",
            business_value="y",
            priority="High",
            classification="SOURCE_BACKED",
            source_references=[],
        )


# --- Story quality invariants (DoD §30 / §24.10 hard requirements) ---

def test_user_story_requires_acceptance_criteria():
    with pytest.raises(ValidationError):
        UserStory(
            story_id="US-2",
            epic_id="EPIC-1",
            title="No AC",
            persona="Customer",
            story_statement="As a customer, I want X, so that Y.",
            business_value="value",
            priority="Medium",
            acceptance_criteria=[],  # empty -> invalid
            confidence=0.5,
            classification="AI_RECOMMENDATION",
        )


def test_user_story_requires_epic_id():
    with pytest.raises(ValidationError):
        _story(epic_id="")


# --- Epic/story parent rule at the ProjectPlan aggregate level ---

def _base_plan_kwargs():
    return dict(
        summary=ProjectSummary(business_problem="p", proposed_solution="s"),
        scope=Scope(),
    )


def test_project_plan_accepts_story_with_valid_epic():
    plan = ProjectPlan(
        **_base_plan_kwargs(),
        epics=[_epic("EPIC-1")],
        stories=[_story("US-1", "EPIC-1")],
    )
    assert plan.stories[0].epic_id == "EPIC-1"


def test_project_plan_rejects_story_with_unknown_epic():
    with pytest.raises(ValidationError, match="unknown epic_id"):
        ProjectPlan(
            **_base_plan_kwargs(),
            epics=[_epic("EPIC-1")],
            stories=[_story("US-1", "EPIC-999")],
        )


def test_project_plan_rejects_duplicate_epic_ids():
    with pytest.raises(ValidationError, match="duplicate epic_id"):
        ProjectPlan(
            **_base_plan_kwargs(),
            epics=[_epic("EPIC-1"), _epic("EPIC-1")],
        )


def test_project_plan_rejects_duplicate_story_ids():
    with pytest.raises(ValidationError, match="duplicate story_id"):
        ProjectPlan(
            **_base_plan_kwargs(),
            epics=[_epic("EPIC-1")],
            stories=[_story("US-1", "EPIC-1"), _story("US-1", "EPIC-1")],
        )


def test_sprint_plan_is_marked_ai_draft_by_default():
    plan = SprintPlan(suggested_sprint_count=2)
    assert plan.is_ai_generated_draft is True

"""Unit tests for run_planning_agent_summary_scope_epics (spec §7.3, §13.3-§13.5) — real
function, mocked LLM calls, real (in-memory) DB. Mirrors the testing style of
test_requirement_analyst_agent.py: `run_agent` is mocked at the point of use so the test
exercises real prompt-construction, real requirement/clarification retrieval, and real
deterministic epic-ID assignment without needing a live Ollama.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models import Base, PlanArtifactVersion, ProjectRecord, RequirementRecord
from app.models.requirement import ClarificationQuestionRecord
from app.schemas.common import SourceReference
from app.schemas.planning import (
    AcceptanceCriterionDraft,
    AssumptionDraft,
    DependencyDraft,
    EpicDraft,
    IssueDraft,
    PlanningEpicsResult,
    PlanningStoriesResult,
    PlanningSummaryScopeResult,
    PlanningTasksDepsRaidResult,
    ProjectSummary,
    RiskDraft,
    Scope,
    Sprint,
    SprintPlan,
    TechnicalTaskDraft,
    UserStoryDraft,
)
from app.schemas.project import ProjectInfo
from app.schemas.requirement import Requirement

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
                grounding_requirement_ids=["REQ-1"],
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


def test_epic_draft_parses_with_source_backed_classification_and_no_citation():
    """Found live: once the prompt told the model grounding_requirement_ids was authoritative
    and source_references merely best-effort, the model stopped filling source_references in
    at all — and GroundedMixin's parse-time "SOURCE_BACKED needs a citation" check then
    rejected every single epic in the batch before Python's backfill (_assign_epic_ids) ever
    ran, crashing the whole Planning node. EpicDraft must accept this shape; the citation
    requirement is enforced later, on the final Epic, after backfill.
    """
    draft = EpicDraft(
        title="Card Payments",
        objective="Let customers pay by card",
        business_value="Unlocks online revenue",
        priority="High",
        classification="SOURCE_BACKED",
        source_references=[],
        grounding_requirement_ids=["REQ-1"],
    )
    assert draft.source_references == []


def test_user_story_draft_parses_with_source_backed_classification_and_no_citation():
    """Same bug, same fix, for UserStoryDraft."""
    draft = UserStoryDraft(
        epic_id="EPIC-001",
        title="Pay with card",
        persona="Customer",
        story_statement="As a customer, I want to pay by card, so that I can complete checkout.",
        business_value="Enables revenue",
        priority="High",
        acceptance_criteria=[
            AcceptanceCriterionDraft(given="a cart", when="I submit valid card details", then="the payment is charged")
        ],
        suggested_story_points=3,
        confidence=0.85,
        classification="SOURCE_BACKED",
        source_references=[],
        grounding_requirement_ids=["REQ-1"],
    )
    assert draft.source_references == []


def test_user_story_draft_rejects_a_missing_or_null_story_point_estimate():
    """Regression test (Day 22, continued): suggested_story_points was changed from
    `int | None = Field(default=None, ge=0)` to a required, non-nullable `int = Field(ge=1)`
    on the DRAFT schema specifically — a prompt instruction alone ("REQUIRED, never null") did
    not change observed live behavior across 2 independent live runs, so null is now removed
    as a legal completion at the JSON-schema level Ollama's constrained decoding uses. The
    final UserStory (not this draft) still allows `None` for legitimate downstream cases.
    """
    from pydantic import ValidationError

    base_kwargs = dict(
        epic_id="EPIC-001",
        title="Pay with card",
        persona="Customer",
        story_statement="As a customer, I want to pay by card, so that I can complete checkout.",
        business_value="Enables revenue",
        priority="High",
        acceptance_criteria=[
            AcceptanceCriterionDraft(given="a cart", when="I submit valid card details", then="the payment is charged")
        ],
        confidence=0.85,
        classification="AI_RECOMMENDATION",
    )

    with pytest.raises(ValidationError):
        UserStoryDraft(**base_kwargs)  # missing entirely

    with pytest.raises(ValidationError):
        UserStoryDraft(**base_kwargs, suggested_story_points=None)  # explicit null

    with pytest.raises(ValidationError):
        UserStoryDraft(**base_kwargs, suggested_story_points=0)  # below ge=1

    draft = UserStoryDraft(**base_kwargs, suggested_story_points=3)
    assert draft.suggested_story_points == 3


def test_dependency_draft_rejects_a_missing_or_empty_description():
    """Regression test (Day 23): description/suggested_resolution were changed from
    `str = ""` to a required, non-empty `Field(min_length=1)` — Day 20 found every sampled
    dependency had these as the schema default (empty string), and Day 22's story-points fix
    established that an optional field with a default is a legal omission under Ollama's
    constrained decoding, regardless of prompt wording.
    """
    from pydantic import ValidationError

    from app.schemas.planning import DependencyDraft

    base_kwargs = dict(
        blocking_item_id="EPIC-001", blocked_item_id="EPIC-002", dependency_type="BLOCKS",
    )

    with pytest.raises(ValidationError):
        DependencyDraft(**base_kwargs, suggested_resolution="Sequence after EPIC-001.")  # missing description

    with pytest.raises(ValidationError):
        DependencyDraft(**base_kwargs, description="", suggested_resolution="x")  # empty

    with pytest.raises(ValidationError):
        DependencyDraft(**base_kwargs, description="x", suggested_resolution="")  # empty resolution

    draft = DependencyDraft(
        **base_kwargs, description="Payments must exist before refunds can be tested.",
        suggested_resolution="Sequence EPIC-002 after EPIC-001.",
    )
    assert draft.description


def test_epic_source_references_backfilled_from_grounding_requirement_ids_even_if_llm_citation_wrong(
    session_factory,
):
    """Found live: the Planning LLM reliably fails to reproduce a chunk_id verbatim (e.g.
    citing 'CH-003' instead of the real 'doc_8cd1399029ed-CH-003'), which silently broke
    every requirement's traceability-matrix link and tripped the dangling-citation validator
    on every epic in a real run. grounding_requirement_ids is a short REQ-XXX token the same
    model copies correctly, so Python uses it to attach the real citation instead of
    trusting the model's own (here, deliberately wrong) source_references.
    """
    wrong_citation = {
        "document_name": "requirements.pdf",
        "page_number": 3,
        "section": "Payments",
        "chunk_id": "CH-003",  # missing the real "DOC-1-" prefix — exactly the live failure
    }
    bad_epics_result = PlanningEpicsResult(
        epics=[
            EpicDraft(
                title="Card Payments",
                objective="Let customers pay by card",
                business_value="Unlocks online revenue",
                priority="High",
                classification="SOURCE_BACKED",
                source_references=[SourceReference(**wrong_citation)],
                grounding_requirement_ids=["REQ-1"],
            )
        ]
    )

    with patch("app.agents.planning.search_company_standards", return_value=[]), patch(
        "app.agents.planning.run_agent",
        side_effect=[_summary_scope_result(), bad_epics_result],
    ):
        from app.agents.planning import run_planning_agent_summary_scope_epics

        _, _, epics = run_planning_agent_summary_scope_epics(
            "PRJ-PLAN", "RUN-1", session_factory=session_factory
        )

    assert epics[0].source_references[0].chunk_id == CITATION["chunk_id"]
    assert epics[0].source_references[0].chunk_id != "CH-003"


def test_epic_fallback_citation_is_still_corrected_when_grounding_does_not_resolve(session_factory):
    """Regression test (Day 23, found via a live run's validation_is_valid: false): when
    grounding_requirement_ids doesn't resolve to any real requirement, _assign_epic_ids falls
    back to the model's own source_references — but that fallback was never corrected against
    real chunk metadata (unlike the grounded path above, and unlike Requirements/RAID items,
    Day 22), letting a real chunk_id's document_name/section stay whatever the model invented.
    Seeds a real DocumentChunkMeta so the correction has something genuine to fix.
    """
    from app.models.document import DocumentChunkMeta, DocumentRecord

    with session_factory() as session:
        session.add(
            DocumentRecord(
                document_id="DOC-2", project_id="PRJ-PLAN", document_name="standards.md",
                file_path="/data/standards.md",
            )
        )
        session.add(
            DocumentChunkMeta(
                chunk_id="DOC-2-CH-007", document_id="DOC-2", project_id="PRJ-PLAN",
                page_number=9, section="Real Section",
            )
        )
        session.commit()

    ungrounded_but_real_chunk = PlanningEpicsResult(
        epics=[
            EpicDraft(
                title="Ungrounded Epic",
                objective="Not linked to any approved requirement",
                business_value="Unclear",
                priority="Low",
                classification="SOURCE_BACKED",
                source_references=[
                    SourceReference(
                        document_name="invented.pdf", page_number=1, section="Invented Section",
                        chunk_id="DOC-2-CH-007",  # real chunk_id, wrong other fields
                    )
                ],
                grounding_requirement_ids=["REQ-DOES-NOT-EXIST"],
            )
        ]
    )

    from app.schemas.planning import EpicCoverageBackfillResult

    with patch("app.agents.planning.search_company_standards", return_value=[]), patch(
        "app.agents.planning.run_agent",
        # 3rd item: this epic's grounding doesn't cover REQ-1 either, so the coverage
        # backfill call (Day 22) also fires — a no-op assignment list is fine, this test is
        # only about the fallback citation correction, not coverage.
        side_effect=[_summary_scope_result(), ungrounded_but_real_chunk, EpicCoverageBackfillResult()],
    ):
        from app.agents.planning import run_planning_agent_summary_scope_epics

        _, _, epics = run_planning_agent_summary_scope_epics(
            "PRJ-PLAN", "RUN-1", session_factory=session_factory
        )

    assert epics[0].source_references[0].document_name == "standards.md"
    assert epics[0].source_references[0].section == "Real Section"


def test_assign_epic_ids_still_rejects_source_backed_epic_with_no_resolvable_grounding(session_factory):
    """The relaxed EpicDraft parsing (no citation check) must not become a silent grounding
    bypass: if grounding_requirement_ids doesn't resolve to any real requirement AND the model
    also left source_references empty, the final Epic construction must still raise — this is
    the strict-grounding invariant (spec §12.4/§12.5), just enforced one step later than
    before (after backfill instead of at LLM-output parse time).
    """
    from pydantic import ValidationError

    from app.agents.planning import _assign_epic_ids

    ungrounded_draft = EpicDraft(
        title="Ghost Epic",
        objective="Not grounded in anything real",
        business_value="None",
        priority="Low",
        classification="SOURCE_BACKED",
        source_references=[],
        grounding_requirement_ids=["REQ-DOES-NOT-EXIST"],
    )

    with pytest.raises(ValidationError):
        _assign_epic_ids([ungrounded_draft], [_requirement()], "PRJ-PLAN", session_factory=session_factory)


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


def test_planning_agent_summary_scope_epics_includes_revision_instructions(session_factory):
    from app.agents.planning import run_planning_agent_summary_scope_epics
    from app.schemas.reviewer import ReviewerIssue

    instructions = [
        ReviewerIssue(
            artifact_id="US-007", issue_type="MISSING_ACCEPTANCE_CRITERIA",
            description="The story does not define the failed-payment scenario.",
            recommended_action="Add acceptance criteria for payment rejection and retry.",
        )
    ]

    with patch("app.agents.planning.search_company_standards", return_value=[]), patch(
        "app.agents.planning.run_agent",
        side_effect=[_summary_scope_result(), _epics_result()],
    ) as mock_run_agent:
        run_planning_agent_summary_scope_epics(
            "PRJ-PLAN", "RUN-1", session_factory=session_factory, revision_instructions=instructions,
        )

    for call in mock_run_agent.call_args_list:
        prompt = call.kwargs["prompt"]
        assert "US-007" in prompt
        assert "Add acceptance criteria for payment rejection and retry." in prompt


# --- User stories + acceptance criteria (Day 12, spec §13.6) ---

def _project_info() -> ProjectInfo:
    return ProjectInfo(
        project_id="PRJ-PLAN",
        name="E-commerce Payments",
        description="Add payment processing to the storefront.",
        methodology="agile_scrum",
    )


def _requirement() -> Requirement:
    return Requirement(
        requirement_id="REQ-1",
        title="Card payment",
        description="Customers must be able to pay by card.",
        category="functional",
        classification="SOURCE_BACKED",
        confidence=0.9,
        source_references=[SourceReference(**CITATION)],
    )


def _epics() -> list:
    from app.agents.planning import _assign_epic_ids

    # session_factory=None is safe here: _epics_result()'s one ungrounded epic (EPIC-002) has
    # empty source_references, so correct_source_references' fast path (`if not refs: return
    # refs`) returns before ever touching a session_factory.
    return _assign_epic_ids(_epics_result().epics, [_requirement()], "PRJ-PLAN", session_factory=None)


def _requirement_2() -> Requirement:
    return Requirement(
        requirement_id="REQ-2",
        title="Refunds",
        description="Customers must be able to request a refund.",
        category="functional",
        classification="SOURCE_BACKED",
        confidence=0.9,
        source_references=[SourceReference(**CITATION)],
    )


def test_backfill_epic_coverage_returns_epics_unchanged_when_nothing_uncovered():
    """Day 22: the backfill call must cost nothing (no LLM call at all) when the main epics
    call already covered every approved requirement — the common case for a well-behaved run.
    """
    from app.agents.planning import _backfill_epic_coverage

    epics = _epics()
    with patch("app.agents.planning.run_agent") as mock_run_agent:
        result = _backfill_epic_coverage(epics, [_requirement()], [])

    mock_run_agent.assert_not_called()
    assert result == epics


def test_backfill_epic_coverage_assigns_an_uncovered_requirement_to_the_chosen_epic():
    """Day 22: REQ-2 is not covered by any epic from _epics() (only REQ-1 is grounded on
    EPIC-001). The backfill call proposes REQ-2 -> EPIC-001; the merged epic must carry both
    requirement_ids in grounding_requirement_ids and a real citation for the newly added one.
    """
    from app.agents.planning import _backfill_epic_coverage
    from app.schemas.planning import EpicCoverageAssignment, EpicCoverageBackfillResult

    epics = _epics()
    backfill_result = EpicCoverageBackfillResult(
        assignments=[EpicCoverageAssignment(requirement_id="REQ-2", epic_id="EPIC-001")]
    )

    with patch("app.agents.planning.run_agent", return_value=backfill_result):
        updated = _backfill_epic_coverage(epics, [_requirement(), _requirement_2()], ["REQ-2"])

    epic = next(e for e in updated if e.epic_id == "EPIC-001")
    assert set(epic.grounding_requirement_ids) == {"REQ-1", "REQ-2"}
    assert any(ref.chunk_id == CITATION["chunk_id"] for ref in epic.source_references)


def test_backfill_epic_coverage_ignores_assignment_to_unknown_epic():
    """A backfill assignment referencing an epic_id that doesn't exist must be dropped, not
    trusted — mirrors _filter_stories_with_unknown_epic's existing safety pattern.
    """
    from app.agents.planning import _backfill_epic_coverage
    from app.schemas.planning import EpicCoverageAssignment, EpicCoverageBackfillResult

    epics = _epics()
    backfill_result = EpicCoverageBackfillResult(
        assignments=[EpicCoverageAssignment(requirement_id="REQ-2", epic_id="EPIC-999")]
    )

    with patch("app.agents.planning.run_agent", return_value=backfill_result):
        updated = _backfill_epic_coverage(epics, [_requirement(), _requirement_2()], ["REQ-2"])

    assert updated == epics


def test_run_planning_agent_summary_scope_epics_backfills_uncovered_requirement(session_factory):
    """Integration-level proof (Day 22): a second requirement (REQ-2) that the main epics call
    leaves uncovered gets picked up by the automatic backfill pass within
    run_planning_agent_summary_scope_epics itself, with no extra plumbing required by callers.
    """
    from app.agents.planning import run_planning_agent_summary_scope_epics
    from app.schemas.planning import EpicCoverageAssignment, EpicCoverageBackfillResult

    with session_factory() as session:
        session.add(
            RequirementRecord(
                requirement_id="REQ-2",
                project_id="PRJ-PLAN",
                workflow_run_id="RUN-0",
                title="Refunds",
                category="functional",
                classification="SOURCE_BACKED",
                confidence=0.9,
                payload_json={
                    "requirement_id": "REQ-2",
                    "title": "Refunds",
                    "description": "Customers must be able to request a refund.",
                    "category": "functional",
                    "classification": "SOURCE_BACKED",
                    "confidence": 0.9,
                    "source_references": [CITATION],
                },
            )
        )
        session.commit()

    backfill_result = EpicCoverageBackfillResult(
        assignments=[EpicCoverageAssignment(requirement_id="REQ-2", epic_id="EPIC-001")]
    )

    with patch("app.agents.planning.search_company_standards", return_value=[]), patch(
        "app.agents.planning.run_agent",
        side_effect=[_summary_scope_result(), _epics_result(), backfill_result],
    ):
        _, _, epics = run_planning_agent_summary_scope_epics(
            "PRJ-PLAN", "RUN-1", session_factory=session_factory
        )

    epic = next(e for e in epics if e.epic_id == "EPIC-001")
    assert "REQ-2" in epic.grounding_requirement_ids


def _stories_draft_result() -> PlanningStoriesResult:
    return PlanningStoriesResult(
        stories=[
            UserStoryDraft(
                epic_id="EPIC-001",
                title="Pay with card",
                persona="Customer",
                story_statement="As a customer, I want to pay by card, so that I can complete checkout.",
                business_value="Enables revenue",
                priority="High",
                acceptance_criteria=[
                    AcceptanceCriterionDraft(
                        given="a cart", when="I submit valid card details", then="the payment is charged"
                    ),
                    AcceptanceCriterionDraft(
                        given="a cart", when="I submit an invalid card", then="I see an error and am not charged"
                    ),
                ],
                suggested_story_points=5,
                confidence=0.85,
                classification="SOURCE_BACKED",
                source_references=[SourceReference(**CITATION)],
                grounding_requirement_ids=["REQ-1"],
            )
        ]
    )


def test_generate_stories_assigns_sequential_ids_and_preserves_citation():
    from app.agents.planning import _generate_stories

    with patch("app.agents.planning.run_agent", return_value=_stories_draft_result()):
        stories = _generate_stories(_project_info(), [_requirement()], [], [], _epics(), "PRJ-PLAN")

    assert len(stories) == 1
    story = stories[0]
    assert story.story_id == "US-001"
    assert [ac.criterion_id for ac in story.acceptance_criteria] == ["AC-001", "AC-002"]
    assert story.source_references[0].chunk_id == CITATION["chunk_id"]


def test_generate_stories_drops_story_referencing_unknown_epic():
    from app.agents.planning import _generate_stories

    bad_result = PlanningStoriesResult(
        stories=[
            UserStoryDraft(
                epic_id="EPIC-999",
                title="Ghost story",
                persona="Customer",
                story_statement="As a customer, I want a ghost feature, so that nothing happens.",
                business_value="None",
                priority="Low",
                acceptance_criteria=[AcceptanceCriterionDraft(given="x", when="y", then="z")],
                suggested_story_points=2,
                confidence=0.5,
                classification="AI_RECOMMENDATION",
            )
        ]
    )

    with patch("app.agents.planning.run_agent", return_value=bad_result):
        stories = _generate_stories(_project_info(), [_requirement()], [], [], _epics(), "PRJ-PLAN")

    assert stories == []


def test_generate_stories_prompt_includes_valid_epic_ids_and_format_rules():
    from app.agents.planning import _generate_stories

    with patch("app.agents.planning.run_agent", return_value=_stories_draft_result()) as mock_run_agent:
        _generate_stories(_project_info(), [_requirement()], [], [], _epics(), "PRJ-PLAN")

    prompt = mock_run_agent.call_args.kwargs["prompt"]
    assert "EPIC-001" in prompt
    assert "As a [persona], I want" in prompt
    assert "technolog" in prompt.lower()


# --- Technical tasks, dependencies, RAID log (Day 12, spec §13.7-§13.9) ---

def _story():
    from app.agents.planning import _assign_story_and_ac_ids

    return _assign_story_and_ac_ids(_stories_draft_result().stories, [_requirement()], "PRJ-PLAN")[0]


def _tasks_deps_raid_draft_result() -> PlanningTasksDepsRaidResult:
    return PlanningTasksDepsRaidResult(
        technical_tasks=[
            TechnicalTaskDraft(story_id="US-001", category="Backend", description="Integrate Stripe API"),
            TechnicalTaskDraft(story_id="US-999", category="Testing", description="Test payment retries"),
        ],
        dependencies=[
            DependencyDraft(
                blocking_item_id="EPIC-001", blocked_item_id="US-001", dependency_type="BLOCKS",
                description="EPIC-001 must ship the payment epic before US-001 can be tested.",
                suggested_resolution="Sequence US-001 after EPIC-001 is delivered.",
            ),
            DependencyDraft(
                blocking_item_id="EPIC-001", blocked_item_id="US-999", dependency_type="BLOCKS",
                description="EPIC-001 must ship the payment epic before US-999 can be tested.",
                suggested_resolution="Sequence US-999 after EPIC-001 is delivered.",
            ),
        ],
        risks=[
            RiskDraft(
                description="Stripe outage blocks checkout",
                probability="Low",
                impact="High",
                severity="Medium",
                mitigation="Add retry with backoff",
                contingency="Fallback to manual invoicing",
                classification="AI_RECOMMENDATION",
            )
        ],
        assumptions=[
            AssumptionDraft(description="Stripe is the chosen provider", classification="CLARIFICATION_BACKED")
        ],
        issues=[IssueDraft(description="No sandbox credentials yet")],
    )


def test_generate_tasks_deps_raid_assigns_sequential_ids():
    from app.agents.planning import _generate_tasks_deps_raid

    with patch("app.agents.planning.run_agent", return_value=_tasks_deps_raid_draft_result()):
        tasks, raid = _generate_tasks_deps_raid(_project_info(), [_requirement()], [], [], _epics(), [_story()])

    assert [t.task_id for t in tasks] == ["TASK-001", "TASK-002"]
    assert [r.risk_id for r in raid.risks] == ["RISK-001"]
    assert [a.assumption_id for a in raid.assumptions] == ["ASSUMP-001"]
    assert [i.issue_id for i in raid.issues] == ["ISSUE-001"]


def test_generate_tasks_deps_raid_nulls_unknown_story_reference():
    from app.agents.planning import _generate_tasks_deps_raid

    with patch("app.agents.planning.run_agent", return_value=_tasks_deps_raid_draft_result()):
        tasks, _ = _generate_tasks_deps_raid(_project_info(), [_requirement()], [], [], _epics(), [_story()])

    by_description = {t.description: t for t in tasks}
    assert by_description["Integrate Stripe API"].story_id == "US-001"
    assert by_description["Test payment retries"].story_id is None


def test_generate_tasks_deps_raid_drops_dependency_with_unknown_endpoint():
    from app.agents.planning import _generate_tasks_deps_raid

    with patch("app.agents.planning.run_agent", return_value=_tasks_deps_raid_draft_result()):
        _, raid = _generate_tasks_deps_raid(_project_info(), [_requirement()], [], [], _epics(), [_story()])

    assert len(raid.dependencies) == 1
    assert raid.dependencies[0].blocked_item_id == "US-001"


def test_generate_tasks_deps_raid_preserves_risk_classification():
    from app.agents.planning import _generate_tasks_deps_raid

    with patch("app.agents.planning.run_agent", return_value=_tasks_deps_raid_draft_result()):
        _, raid = _generate_tasks_deps_raid(_project_info(), [_requirement()], [], [], _epics(), [_story()])

    assert raid.risks[0].classification == "AI_RECOMMENDATION"
    assert raid.risks[0].source_references == []


# --- Sprint plan, traceability matrix, and full pipeline persistence (Day 12, §13.10-§13.11) ---

def _sprint_plan_draft() -> SprintPlan:
    return SprintPlan(
        suggested_sprint_count=1,
        sprints=[Sprint(sprint_number=5, sprint_goal="Ship", story_ids=["US-001", "US-999"], story_point_total=5)],
        unscheduled_story_ids=["US-999"],
    )


def test_generate_sprint_plan_drops_unknown_story_and_renumbers():
    from app.agents.planning import _generate_sprint_plan

    with patch("app.agents.planning.run_agent", return_value=_sprint_plan_draft()):
        plan = _generate_sprint_plan(_project_info(), [_story()])

    assert plan.sprints[0].sprint_number == 1
    assert plan.sprints[0].story_ids == ["US-001"]
    assert plan.unscheduled_story_ids == []


def test_build_traceability_matrix_links_requirement_epic_story():
    from app.agents.planning import _build_traceability_matrix

    matrix = _build_traceability_matrix([_requirement()], _epics(), [_story()])

    row = next(r for r in matrix.rows if r.requirement_id == "REQ-1" and r.story_id == "US-001")
    assert row.epic_id == "EPIC-001"
    assert row.acceptance_criterion_ids == ["AC-001", "AC-002"]


def test_build_traceability_matrix_flags_coverage_gap_for_unmatched_requirement():
    from app.agents.planning import _build_traceability_matrix

    orphan = Requirement(
        requirement_id="REQ-2",
        title="Refunds",
        description="Customers can request refunds.",
        category="functional",
        classification="ASSUMPTION",
        confidence=0.4,
    )
    matrix = _build_traceability_matrix([_requirement(), orphan], _epics(), [_story()])

    gap_row = next(r for r in matrix.rows if r.requirement_id == "REQ-2")
    assert gap_row.epic_id is None
    assert gap_row.story_id is None


def test_run_planning_agent_produces_and_persists_full_plan(session_factory):
    with patch("app.agents.planning.search_company_standards", return_value=[]), patch(
        "app.agents.planning.run_agent",
        side_effect=[
            _summary_scope_result(),
            _epics_result(),
            _stories_draft_result(),
            _tasks_deps_raid_draft_result(),
            _sprint_plan_draft(),
        ],
    ):
        from app.agents.planning import run_planning_agent

        plan = run_planning_agent("PRJ-PLAN", "RUN-1", session_factory=session_factory)

    assert plan.epics[0].epic_id == "EPIC-001"
    assert plan.stories[0].story_id == "US-001"
    assert plan.stories[0].epic_id == "EPIC-001"
    assert len(plan.technical_tasks) == 2
    assert plan.sprint_plan.sprints[0].story_ids == ["US-001"]
    assert any(row.story_id == "US-001" for row in plan.traceability.rows)

    session = session_factory()
    saved = session.execute(
        select(PlanArtifactVersion).where(PlanArtifactVersion.project_id == "PRJ-PLAN")
    ).scalars().all()
    session.close()
    assert len(saved) == 1
    assert saved[0].is_current is True
    assert saved[0].version_number == 1

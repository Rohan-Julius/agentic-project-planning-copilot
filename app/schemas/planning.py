"""Planning Agent output schemas (spec §7.3, §13.3–§13.11, §14).

Methodology is Agile/Scrum only (project decision) — only a sprint plan is modeled; the
milestone-plan branch of spec §13.10 is intentionally not implemented (see
docs/ARCHITECTURE.md §5b).
"""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import GroundedMixin, SourceReference
from app.schemas.enums import Classification, DependencyType, ImpactLevel, Priority, TechnicalTaskCategory


class _DraftGrounding(BaseModel):
    """Same shape as GroundedMixin but WITHOUT the SOURCE_BACKED-needs-citation validator.

    Used only by EpicDraft/UserStoryDraft, whose source_references get deterministically
    backfilled from grounding_requirement_ids after parsing (see Epic.grounding_requirement_ids
    docstring) — enforcing citation-presence at LLM-output parse time is redundant for these
    two now, and actively harmful: once the prompt told the model grounding_requirement_ids
    was authoritative and source_references merely best-effort, the model stopped reliably
    filling source_references at all, and GroundedMixin's parse-time check then failed EVERY
    SOURCE_BACKED epic in the batch — a single bad epic used to fail alone, but this crashed
    the whole Planning node before the backfill in _assign_epic_ids ever got a chance to run
    (found live). The strict check still applies to the final Epic/UserStory, after backfill.
    """

    classification: Classification
    source_references: list[SourceReference] = Field(default_factory=list)


class ProjectSummary(BaseModel):
    """Spec §13.3."""

    business_problem: str
    proposed_solution: str
    objectives: list[str] = Field(default_factory=list)
    target_users: list[str] = Field(default_factory=list)
    expected_benefits: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    major_constraints: list[str] = Field(default_factory=list)


class Scope(BaseModel):
    """Spec §13.4."""

    in_scope: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    future_scope: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)


class AcceptanceCriterion(BaseModel):
    """Given/When/Then format (spec §7.3 "Acceptance-criteria format")."""

    criterion_id: str
    given: str
    when: str
    then: str


class Epic(GroundedMixin):
    """Spec §13.5."""

    epic_id: str = Field(min_length=1)
    title: str
    objective: str
    business_value: str
    description: str = ""
    priority: Priority
    dependencies: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    # Which approved requirement_id(s) this epic is grounded in (e.g. "REQ-003") — the
    # authoritative link the deterministic traceability matrix joins on. Kept separate from
    # `source_references`: a small model reliably fails to reproduce a chunk_id character
    # for character (found live — every epic in a real run cited a truncated chunk_id that
    # matched no real chunk, silently breaking the traceability matrix and failing the
    # dangling-citation validator). Copying a short REQ-XXX token it already sees verbatim
    # is a task the same model gets right; `_assign_epic_ids` uses this field to attach the
    # real citation from the referenced requirement(s) instead of trusting the model's own
    # copy of `source_references`.
    grounding_requirement_ids: list[str] = Field(default_factory=list)


class EpicDraft(_DraftGrounding):
    """LLM-facing epic shape for the Planning Agent's epics-generation call (DESIGN.md §0.2,
    §8.3): identical to `Epic` except it has no `epic_id` (IDs are minted deterministically
    after generation, never proposed by the model) and uses `_DraftGrounding` instead of
    `GroundedMixin` — see that class's docstring for why the citation check is deferred.
    """

    title: str
    objective: str
    business_value: str
    description: str = ""
    priority: Priority
    dependencies: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    grounding_requirement_ids: list[str] = Field(default_factory=list)


class PlanningSummaryScopeResult(BaseModel):
    """Output shape of the Planning Agent's first generation call (DESIGN.md §8.3
    "Generation order": summary+scope → epics → ...)."""

    summary: ProjectSummary
    scope: Scope


class PlanningEpicsResult(BaseModel):
    """Output shape of the Planning Agent's second generation call (epics)."""

    epics: list[EpicDraft] = Field(default_factory=list)


class EpicCoverageAssignment(BaseModel):
    """One requirement→epic assignment proposed by the coverage-backfill call (Day 22, spec
    §24.10 — every approved requirement must be represented somewhere in the plan)."""

    requirement_id: str
    epic_id: str


class EpicCoverageBackfillResult(BaseModel):
    """Output shape of the Planning Agent's optional coverage-backfill call (Day 22) — only
    invoked when the main epics call leaves at least one approved requirement uncovered by
    every epic's grounding_requirement_ids. See `_backfill_epic_coverage` in
    app/agents/planning.py for why a second, narrowly-scoped call exists on top of the
    epics-prompt COVERAGE instruction rather than relying on the prompt alone.
    """

    assignments: list[EpicCoverageAssignment] = Field(default_factory=list)


class AcceptanceCriterionDraft(BaseModel):
    """LLM-facing AC shape (DESIGN.md §0.2): identical to AcceptanceCriterion minus
    criterion_id — IDs are minted deterministically after generation."""

    given: str
    when: str
    then: str


class UserStoryDraft(_DraftGrounding):
    """LLM-facing story shape (DESIGN.md §0.2, §8.3): identical to UserStory minus
    story_id and each AC's criterion_id. `epic_id` IS supplied by the model — it is a
    reference to an already-minted Epic, not a new identity being proposed. Uses
    `_DraftGrounding` instead of `GroundedMixin` — see that class's docstring for why.
    """

    epic_id: str = Field(min_length=1)
    title: str
    persona: str
    story_statement: str
    business_value: str
    priority: Priority
    acceptance_criteria: list[AcceptanceCriterionDraft] = Field(min_length=1)
    dependencies: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    # Day 22: was `int | None = Field(default=None, ge=0)`, which compiles to a nullable
    # {"anyOf": [integer, null]} JSON schema for Ollama's format=schema constrained decoding.
    # A prompt instruction alone ("REQUIRED, never null") did not change the observed live
    # behavior across 2 independent live runs (0/18, 0/27 stories) — the model consistently
    # picked null. Making the DRAFT field a required, non-nullable int removes null as a
    # legal completion at the grammar level, forcing a real number regardless of what the
    # prose says. The final UserStory below deliberately stays `int | None` — a legitimate
    # "not yet estimated" state remains representable downstream even if the model, in
    # constrained decoding, can no longer produce it directly at this call site.
    suggested_story_points: int = Field(ge=1)
    confidence: float = Field(ge=0.0, le=1.0)
    grounding_requirement_ids: list[str] = Field(default_factory=list)


class PlanningStoriesResult(BaseModel):
    """Output shape of the Planning Agent's third generation call (stories + AC)."""

    stories: list[UserStoryDraft] = Field(default_factory=list)


class UserStory(GroundedMixin):
    """Spec §13.6, §14 example.

    `epic_id` (non-empty) and `acceptance_criteria` (>=1 entry) are schema invariants, not
    just Reviewer checks — the DoD (§30) and quantitative targets (§24.10) treat "every
    story belongs to an epic" and "every story has acceptance criteria" as hard requirements,
    so invalid output is caught immediately by the retry-once policy (§14) rather than only
    surfacing later at review time. See docs/DAY2_UNDERSTANDING.md point 2.
    """

    story_id: str
    epic_id: str = Field(min_length=1)
    title: str
    persona: str
    story_statement: str
    business_value: str
    priority: Priority
    acceptance_criteria: list[AcceptanceCriterion] = Field(min_length=1)
    dependencies: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    suggested_story_points: int | None = Field(default=None, ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
    grounding_requirement_ids: list[str] = Field(default_factory=list)


class TechnicalTask(BaseModel):
    """Recommendation, not a confirmed technical requirement (spec §13.7)."""

    task_id: str
    story_id: str | None = None
    category: TechnicalTaskCategory
    description: str
    is_recommendation: bool = True


class Dependency(BaseModel):
    """Spec §13.8."""

    dependency_id: str
    blocking_item_id: str
    blocked_item_id: str
    dependency_type: DependencyType
    description: str = ""
    suggested_resolution: str = ""


class Risk(GroundedMixin):
    """A RAID risk entry (spec §13.9)."""

    risk_id: str
    description: str
    probability: ImpactLevel
    impact: ImpactLevel
    severity: ImpactLevel
    mitigation: str
    contingency: str


class Assumption(GroundedMixin):
    """A RAID assumption entry (spec §13.9)."""

    assumption_id: str
    description: str


class Issue(BaseModel):
    """A RAID issue entry (spec §13.9)."""

    issue_id: str
    description: str
    status: str = "OPEN"
    source_references: list[SourceReference] = Field(default_factory=list)


class TechnicalTaskDraft(BaseModel):
    """LLM-facing technical-task shape (DESIGN.md §0.2): identical to TechnicalTask minus
    task_id."""

    story_id: str | None = None
    category: TechnicalTaskCategory
    description: str


class DependencyDraft(BaseModel):
    """LLM-facing dependency shape (DESIGN.md §0.2): identical to Dependency minus
    dependency_id."""

    blocking_item_id: str
    blocked_item_id: str
    dependency_type: DependencyType
    # Day 23: was `str = ""` for both — Day 20 found every sampled dependency had these as the
    # schema default (empty string), never real content. Day 22 established that an optional
    # field with a default gets silently omitted under Ollama's constrained decoding; a
    # required, non-empty field removes that as a legal completion at the schema level.
    description: str = Field(min_length=1)
    suggested_resolution: str = Field(min_length=1)


class RiskDraft(GroundedMixin):
    """LLM-facing risk shape (DESIGN.md §0.2): identical to Risk minus risk_id."""

    description: str
    probability: ImpactLevel
    impact: ImpactLevel
    severity: ImpactLevel
    mitigation: str
    contingency: str


class AssumptionDraft(GroundedMixin):
    """LLM-facing assumption shape (DESIGN.md §0.2): identical to Assumption minus
    assumption_id."""

    description: str


class IssueDraft(BaseModel):
    """LLM-facing issue shape (DESIGN.md §0.2): identical to Issue minus issue_id."""

    description: str
    status: str = "OPEN"
    source_references: list[SourceReference] = Field(default_factory=list)


class PlanningTasksDepsRaidResult(BaseModel):
    """Output shape of the Planning Agent's fourth generation call (tasks + dependencies +
    RAID)."""

    technical_tasks: list[TechnicalTaskDraft] = Field(default_factory=list)
    dependencies: list[DependencyDraft] = Field(default_factory=list)
    risks: list[RiskDraft] = Field(default_factory=list)
    assumptions: list[AssumptionDraft] = Field(default_factory=list)
    issues: list[IssueDraft] = Field(default_factory=list)


class RaidLog(BaseModel):
    """Spec §13.9."""

    risks: list[Risk] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
    dependencies: list[Dependency] = Field(default_factory=list)


class Sprint(BaseModel):
    """One sprint within the Agile sprint plan (spec §13.10, Agile/Scrum branch)."""

    sprint_number: int = Field(ge=1)
    sprint_goal: str
    story_ids: list[str] = Field(default_factory=list)
    story_point_total: int = Field(ge=0)


class SprintPlan(BaseModel):
    """Agile/Scrum delivery plan (spec §13.10). Always AI-draft, always human-reviewed.

    The milestone-plan alternative in §13.10 is not modeled — see project methodology
    decision in docs/ARCHITECTURE.md §5b.
    """

    is_ai_generated_draft: bool = True
    suggested_sprint_count: int = Field(ge=1)
    sprints: list[Sprint] = Field(default_factory=list)
    dependency_considerations: list[str] = Field(default_factory=list)
    unscheduled_story_ids: list[str] = Field(default_factory=list)


class TraceabilityRow(BaseModel):
    """One row of the traceability matrix (spec §13.11)."""

    requirement_id: str
    source_references: list[SourceReference] = Field(default_factory=list)
    epic_id: str | None = None
    story_id: str | None = None
    acceptance_criterion_ids: list[str] = Field(default_factory=list)


class TraceabilityMatrix(BaseModel):
    rows: list[TraceabilityRow] = Field(default_factory=list)


class PlanVersionSummary(BaseModel):
    """Metadata for one persisted plan version (spec §22) — no plan_json payload, so listing
    every version stays cheap. Use GET .../plan/versions/{version_id} for one version's full
    plan content."""

    version_id: str
    version_number: int
    model: str
    prompt_version: str
    reviewer_decision: str | None
    is_current: bool
    generated_at: dt.datetime


class ProjectPlan(BaseModel):
    """The full Planning Agent output (spec §7.3 "Tasks").

    Cross-artifact invariants that don't require a database are validated here (every
    story's epic_id must resolve within this same plan; epic_id/story_id must be unique
    within the plan). Full duplicate-ID and circular-dependency checks against the
    *persisted* plan remain the Day-13 deterministic `validate_project_plan` tool (§9.8) —
    this is a cheap early guard, not a replacement for it (see docs/DAY2_UNDERSTANDING.md
    point 3).
    """

    summary: ProjectSummary
    scope: Scope
    epics: list[Epic] = Field(default_factory=list)
    stories: list[UserStory] = Field(default_factory=list)
    technical_tasks: list[TechnicalTask] = Field(default_factory=list)
    raid: RaidLog = Field(default_factory=RaidLog)
    sprint_plan: SprintPlan | None = None
    traceability: TraceabilityMatrix = Field(default_factory=TraceabilityMatrix)

    @model_validator(mode="after")
    def _validate_cross_references(self) -> "ProjectPlan":
        epic_ids = [e.epic_id for e in self.epics]
        if len(epic_ids) != len(set(epic_ids)):
            raise ValueError("duplicate epic_id within ProjectPlan")

        story_ids = [s.story_id for s in self.stories]
        if len(story_ids) != len(set(story_ids)):
            raise ValueError("duplicate story_id within ProjectPlan")

        epic_id_set = set(epic_ids)
        for story in self.stories:
            if story.epic_id not in epic_id_set:
                raise ValueError(
                    f"story {story.story_id!r} references unknown epic_id {story.epic_id!r} "
                    "(every story must belong to an epic in the same plan, spec §7.3/§30)"
                )
        return self

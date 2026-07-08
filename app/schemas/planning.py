"""Planning Agent output schemas (spec §7.3, §13.3–§13.11, §14).

Methodology is Agile/Scrum only (project decision) — only a sprint plan is modeled; the
milestone-plan branch of spec §13.10 is intentionally not implemented (see
docs/ARCHITECTURE.md §5b).
"""
from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import GroundedMixin, SourceReference
from app.schemas.enums import DependencyType, ImpactLevel, Priority, TechnicalTaskCategory


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

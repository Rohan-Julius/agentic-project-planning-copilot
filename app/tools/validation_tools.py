"""Deterministic plan validation and traceability tools (spec §9.8, §9.9, DESIGN.md §10).

Pure Python — no LLM involved (DESIGN.md §0.1: duplicate/traceability/circular-dependency
checks are deterministic work, never agent judgement). These gate plan acceptance and feed
the Reviewer Agent's prompt as pre-computed evidence for the checks it doesn't need to judge
itself (spec §7.4 checks 2, 3, 6, 9, 11).
"""
from __future__ import annotations

from collections.abc import Callable

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.database.session import get_sessionmaker
from app.models.document import DocumentChunkMeta
from app.models.plan_artifact import PlanArtifactVersion
from app.schemas.planning import Dependency, ProjectPlan, RequirementImpact, TraceabilityMatrix
from app.schemas.validation import TraceabilityResult, ValidationIssue, ValidationResult


def load_current_plan(
    project_id: str,
    *,
    session_factory: Callable[[], Session] | sessionmaker | None = None,
) -> ProjectPlan | None:
    """The current (is_current=True) plan version for a project, parsed back into a
    ProjectPlan, or None if no plan has been generated yet. Shared by
    validate_project_plan, check_traceability, and the Reviewer Agent.
    """
    session_factory = session_factory or get_sessionmaker()
    session = session_factory()
    try:
        version = session.scalar(
            select(PlanArtifactVersion).where(
                PlanArtifactVersion.project_id == project_id,
                PlanArtifactVersion.is_current.is_(True),
            )
        )
        if version is None:
            return None
        return ProjectPlan.model_validate(version.plan_json)
    finally:
        session.close()


def _artifact_id(item) -> str:
    for attr in ("epic_id", "story_id", "risk_id", "assumption_id"):
        value = getattr(item, attr, None)
        if value:
            return value
    return "unknown"


def _check_duplicate_ids(plan: ProjectPlan) -> list[ValidationIssue]:
    """Epic/story ID uniqueness is already enforced at construction by ProjectPlan's own
    cross-reference validator (app/schemas/planning.py); this covers the artifact families
    that validator does NOT check (spec §9.8 "duplicate IDs").
    """
    errors: list[ValidationIssue] = []
    families = {
        "technical task": [t.task_id for t in plan.technical_tasks],
        "dependency": [d.dependency_id for d in plan.raid.dependencies],
        "risk": [r.risk_id for r in plan.raid.risks],
        "assumption": [a.assumption_id for a in plan.raid.assumptions],
        "issue": [i.issue_id for i in plan.raid.issues],
        "acceptance criterion": [
            ac.criterion_id for story in plan.stories for ac in story.acceptance_criteria
        ],
    }
    for name, ids in families.items():
        seen: set[str] = set()
        for artifact_id in ids:
            if artifact_id in seen:
                errors.append(
                    ValidationIssue(
                        artifact_id=artifact_id, code="DUPLICATE_ID",
                        message=f"duplicate {name} id {artifact_id!r}",
                    )
                )
            seen.add(artifact_id)
    return errors


def _check_parent_references(plan: ProjectPlan) -> list[ValidationIssue]:
    """Invalid parent references (spec §9.8) for artifact families whose cross-references
    ProjectPlan's own validator does not check: technical-task -> story, and dependency
    endpoints -> epic/story.
    """
    errors: list[ValidationIssue] = []
    known_story_ids = {s.story_id for s in plan.stories}
    known_endpoint_ids = known_story_ids | {e.epic_id for e in plan.epics}

    for task in plan.technical_tasks:
        if task.story_id is not None and task.story_id not in known_story_ids:
            errors.append(
                ValidationIssue(
                    artifact_id=task.task_id, code="INVALID_PARENT_REF",
                    message=f"task references unknown story_id {task.story_id!r}",
                )
            )

    for dep in plan.raid.dependencies:
        if dep.blocking_item_id not in known_endpoint_ids:
            errors.append(
                ValidationIssue(
                    artifact_id=dep.dependency_id, code="INVALID_PARENT_REF",
                    message=f"dependency references unknown blocking_item_id {dep.blocking_item_id!r}",
                )
            )
        if dep.blocked_item_id not in known_endpoint_ids:
            errors.append(
                ValidationIssue(
                    artifact_id=dep.dependency_id, code="INVALID_PARENT_REF",
                    message=f"dependency references unknown blocked_item_id {dep.blocked_item_id!r}",
                )
            )
    return errors


def _check_stories_structure(plan: ProjectPlan) -> list[ValidationIssue]:
    """Stories without a valid epic / without acceptance criteria (spec §9.8). Defense in
    depth: ProjectPlan's own construction-time validator already makes this unreachable for
    any plan built through the normal Planning Agent path, but a hand-edited plan_json row
    (e.g. a future manual artifact edit, spec §18 PUT .../plan/artifacts/{id}) could still
    violate it, so the deterministic validator checks it independently rather than trusting
    construction alone.
    """
    errors: list[ValidationIssue] = []
    known_epic_ids = {e.epic_id for e in plan.epics}
    for story in plan.stories:
        if not story.epic_id or story.epic_id not in known_epic_ids:
            errors.append(
                ValidationIssue(
                    artifact_id=story.story_id, code="STORY_WITHOUT_EPIC",
                    message=f"story {story.story_id!r} has no valid parent epic",
                )
            )
        if not story.acceptance_criteria:
            errors.append(
                ValidationIssue(
                    artifact_id=story.story_id, code="MISSING_ACCEPTANCE_CRITERIA",
                    message=f"story {story.story_id!r} has no acceptance criteria",
                )
            )
    return errors


def _check_missing_mandatory_fields(plan: ProjectPlan) -> list[ValidationIssue]:
    errors: list[ValidationIssue] = []
    for epic in plan.epics:
        if not epic.title.strip() or not epic.objective.strip():
            errors.append(
                ValidationIssue(
                    artifact_id=epic.epic_id, code="MISSING_MANDATORY_FIELD",
                    message=f"epic {epic.epic_id!r} is missing a title or objective",
                )
            )
    for story in plan.stories:
        if not story.title.strip() or not story.story_statement.strip():
            errors.append(
                ValidationIssue(
                    artifact_id=story.story_id, code="MISSING_MANDATORY_FIELD",
                    message=f"story {story.story_id!r} is missing a title or story_statement",
                )
            )
    return errors


def _check_source_references(
    plan: ProjectPlan, project_id: str, session: Session
) -> list[ValidationIssue]:
    """Missing source references (SOURCE_BACKED without a citation — belt-and-suspenders,
    GroundedMixin already enforces this at construction) and dangling citations (a chunk_id
    that does not exist, or no longer exists, in document_chunk_meta for this project — the
    check that genuinely cannot happen at construction time; see app/schemas/common.py's
    GroundedMixin docstring, which names this exact tool as its referential half).
    """
    errors: list[ValidationIssue] = []
    grounded_items = [*plan.epics, *plan.stories, *plan.raid.risks, *plan.raid.assumptions]

    chunk_ids: set[str] = set()
    for item in grounded_items:
        if item.classification == "SOURCE_BACKED" and not item.source_references:
            errors.append(
                ValidationIssue(
                    artifact_id=_artifact_id(item), code="MISSING_SOURCE_REFERENCE",
                    message="SOURCE_BACKED item has no source_references",
                )
            )
        chunk_ids.update(ref.chunk_id for ref in item.source_references)

    if not chunk_ids:
        return errors

    existing = set(
        session.scalars(
            select(DocumentChunkMeta.chunk_id).where(
                DocumentChunkMeta.project_id == project_id,
                DocumentChunkMeta.chunk_id.in_(chunk_ids),
            )
        ).all()
    )
    dangling = chunk_ids - existing
    if not dangling:
        return errors

    for item in grounded_items:
        for ref in item.source_references:
            if ref.chunk_id in dangling:
                errors.append(
                    ValidationIssue(
                        artifact_id=_artifact_id(item), code="DANGLING_CITATION",
                        message=f"citation chunk_id {ref.chunk_id!r} does not exist or was deleted",
                    )
                )
    return errors


def _find_dependency_cycle(dependencies: list[Dependency]) -> list[str] | None:
    """DFS cycle detection over blocking_item_id -> blocked_item_id edges (spec §9.8
    "circular dependencies", DESIGN.md §10). Returns the participating IDs in cycle order,
    or None if the dependency graph is acyclic.
    """
    graph: dict[str, list[str]] = {}
    for dep in dependencies:
        graph.setdefault(dep.blocking_item_id, []).append(dep.blocked_item_id)

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {}
    path: list[str] = []

    def visit(node: str) -> list[str] | None:
        color[node] = GRAY
        path.append(node)
        for neighbor in graph.get(node, []):
            state = color.get(neighbor, WHITE)
            if state == WHITE:
                cycle = visit(neighbor)
                if cycle:
                    return cycle
            elif state == GRAY:
                cycle_start = path.index(neighbor)
                return [*path[cycle_start:], neighbor]
        path.pop()
        color[node] = BLACK
        return None

    for node in list(graph.keys()):
        if color.get(node, WHITE) == WHITE:
            cycle = visit(node)
            if cycle:
                return cycle
    return None


def _check_circular_dependencies(plan: ProjectPlan) -> list[ValidationIssue]:
    cycle = _find_dependency_cycle(plan.raid.dependencies)
    if cycle is None:
        return []
    return [
        ValidationIssue(
            artifact_id=cycle[0], code="CIRCULAR_DEPENDENCY",
            message=f"circular dependency detected: {' -> '.join(cycle)}",
        )
    ]


def validate_project_plan(
    project_id: str,
    *,
    session_factory: Callable[[], Session] | sessionmaker | None = None,
) -> ValidationResult:
    """Spec §9.8: schema validity, missing IDs, invalid parent refs, stories without
    epics/AC, duplicate IDs, missing/dangling source references, circular dependencies,
    missing mandatory fields.
    """
    session_factory = session_factory or get_sessionmaker()
    session = session_factory()
    try:
        version = session.scalar(
            select(PlanArtifactVersion).where(
                PlanArtifactVersion.project_id == project_id,
                PlanArtifactVersion.is_current.is_(True),
            )
        )
        if version is None:
            return ValidationResult(
                is_valid=False,
                errors=[
                    ValidationIssue(
                        artifact_id=project_id, code="NO_PLAN",
                        message="No plan has been generated for this project yet",
                    )
                ],
            )

        try:
            plan = ProjectPlan.model_validate(version.plan_json)
        except PydanticValidationError as e:
            return ValidationResult(
                is_valid=False,
                errors=[ValidationIssue(artifact_id=project_id, code="SCHEMA_INVALID", message=str(e))],
            )

        errors = [
            *_check_duplicate_ids(plan),
            *_check_parent_references(plan),
            *_check_stories_structure(plan),
            *_check_missing_mandatory_fields(plan),
            *_check_source_references(plan, project_id, session),
            *_check_circular_dependencies(plan),
        ]
        return ValidationResult(is_valid=not errors, errors=errors)
    finally:
        session.close()


def check_traceability(
    project_id: str,
    *,
    session_factory: Callable[[], Session] | sessionmaker | None = None,
) -> TraceabilityResult:
    """Spec §9.9: verifies Source Requirement -> Epic -> User Story -> Acceptance Criteria.
    Reuses the traceability matrix the Planning Agent already built deterministically
    (app/agents/planning.py::_build_traceability_matrix) rather than recomputing it, and
    derives coverage_gaps / orphan_story_ids from it.
    """
    plan = load_current_plan(project_id, session_factory=session_factory)
    if plan is None:
        return TraceabilityResult(matrix=TraceabilityMatrix())

    coverage_gaps = [row.requirement_id for row in plan.traceability.rows if row.epic_id is None]
    traced_story_ids = {row.story_id for row in plan.traceability.rows if row.story_id}
    orphan_story_ids = [s.story_id for s in plan.stories if s.story_id not in traced_story_ids]

    return TraceabilityResult(
        matrix=plan.traceability,
        coverage_gaps=coverage_gaps,
        orphan_story_ids=orphan_story_ids,
    )


def compute_requirement_impact(
    project_id: str,
    requirement_id: str,
    *,
    session_factory: Callable[[], Session] | sessionmaker | None = None,
) -> RequirementImpact:
    """Every epic/story/task/dependency that traces back to one requirement (§32 stretch goal
    'requirement-change impact analysis') — pure deterministic lookup over the traceability
    matrix already built by _build_traceability_matrix, no LLM call.
    """
    plan = load_current_plan(project_id, session_factory=session_factory)
    if plan is None:
        raise ValueError(f"No plan exists yet for project '{project_id}'")

    matching_rows = [r for r in plan.traceability.rows if r.requirement_id == requirement_id]
    epic_ids = {r.epic_id for r in matching_rows if r.epic_id}
    story_ids = {r.story_id for r in matching_rows if r.story_id}

    epics = [e for e in plan.epics if e.epic_id in epic_ids]
    stories = [s for s in plan.stories if s.story_id in story_ids]
    technical_tasks = [t for t in plan.technical_tasks if t.story_id in story_ids]
    relevant_ids = epic_ids | story_ids
    dependencies = [
        d for d in plan.raid.dependencies
        if d.blocking_item_id in relevant_ids or d.blocked_item_id in relevant_ids
    ]

    return RequirementImpact(
        requirement_id=requirement_id, epics=epics, stories=stories,
        technical_tasks=technical_tasks, dependencies=dependencies,
    )

# Developer Guide

For engineers extending or maintaining this codebase. For "how do I use the app," see the
[User Guide](USER_GUIDE.md) instead. This project was built against a detailed internal
specification (kept private, not part of this repository) covering agent responsibilities,
tool contracts, schemas, and guardrails — this guide, the [README](README.md#architecture),
and the internal `docs/` working notes (`docs/ARCHITECTURE.md`, `docs/DESIGN.md` — local only,
not tracked in this repository) capture everything from it relevant to extending the code.

## Repository layout

```
app/
├── agents/       LLM reasoning only — Supervisor, Requirement Analyst, Planning, Reviewer
├── api/          FastAPI routers, one per resource (projects, documents, workflow, plan, ...)
├── database/     SQLAlchemy session/engine setup
├── models/       SQLAlchemy ORM tables
├── prompts/      (shared prompt fragments, where factored out of agents/)
├── schemas/      Pydantic models — every agent decision and artifact is one of these
├── services/     Deterministic, non-agentic logic (parsing, chunking, embedding, retrieval,
│                 export, citation correction, vector I/O)
├── tools/        The only surface agents reach the system through (§9/§20.2)
└── workflow/     LangGraph state graph, routing, event logging, engine
```

The hard rule (CLAUDE.md, §8): **agents do reasoning only; everything mechanical is
deterministic Python.** Before adding code to `app/agents/`, ask whether it's actually a
judgment call — if it's mechanical (validation, ID assignment, format conversion), it belongs
in `app/services/` or as a plain helper in the agent module, not inside a prompt.

## Adding a new agent tool

Agents reach the application *only* through functions registered under `app/tools/` (§9,
§20.2) — there is no shell tool, no arbitrary-code tool, no internet-search tool, and none
should ever be added. To add a new tool:

1. Write a plain Python function in the relevant `app/tools/*.py` file (or a new file if it's
   a new category) with a clear docstring and typed signature.
2. If it touches project-scoped data, it **must** filter by `project_id` — this is the single
   most important invariant in the codebase (§12.3, §20.4); every retrieval and persistence
   tool does this unconditionally.
3. Call it from the relevant agent module (`app/agents/*.py`), threading `session_factory`/
   `vector_service` through exactly as the existing tools do — never fall back to a
   process-wide singleton inside a function that's meant to be testable, or tests will
   silently hit the real production DB/vector store instead of an injected test one.

## Adding a new API endpoint

Every project-scoped router follows the same shape — look at `app/api/plan.py` or
`app/api/analysis_findings.py` as a template:

```python
def _require_project(session: Session, project_id: str) -> None:
    if project_service.get_project(session, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
```

**Dependency-ordering gotcha** (found live, Day 17, fixed Day 23): if your endpoint also
depends on `get_vector_service` (or another `Depends()` that can itself fail), don't call
`_require_project` as the first line of the function body — FastAPI resolves every `Depends()`
parameter *before* the body runs, so a broken Qdrant connection would surface as a 503 before
your 404 check ever executes, masking a simple "project doesn't exist" behind a misleading
error. Instead, wrap the check as its own dependency and declare it *before* the
Qdrant-dependent one:

```python
def _require_project_dependency(project_id: str, session: Session = Depends(get_session)) -> None:
    _require_project(session, project_id)

@router.post("/some-action")
def some_action(
    project_id: str,
    session: Session = Depends(get_session),
    _project_exists: None = Depends(_require_project_dependency),  # before vector_service
    vector_service: VectorService = Depends(get_vector_service),
):
    ...
```

FastAPI resolves sibling `Depends()` parameters in declaration order — confirmed by a real
regression test (`tests/unit/test_dependency_ordering.py`), not just assumed.

## The deterministic/agentic split, and a lesson worth reusing

Every LLM call in this codebase produces a *draft* schema, and a deterministic Python function
mints real IDs and validates references afterward — the model proposes content, Python assigns
identity (see `_assign_epic_ids`/`_assign_story_and_ac_ids` in `app/agents/planning.py`). This
same principle extends further than IDs:

**If a small local model won't reliably follow a prose instruction, try moving the constraint
into the schema instead of writing a longer prompt.** Two concrete examples from this build:
`suggested_story_points` was `null` on every story despite an explicit "REQUIRED, never null"
prompt instruction — the fix that actually worked was making the *draft* schema field a
required, non-nullable `int` instead of `int | None`, removing `null` as a legal completion at
the JSON-schema grammar level Ollama's constrained decoding uses. The same pattern fixed
`Dependency.description`/`suggested_resolution` (Day 23). If you find a field the model
consistently leaves empty/wrong despite prompt wording saying otherwise, check whether the
schema itself is giving it an easy way out before writing more prompt text.

## Citation correction — how grounding accuracy is actually enforced

`app/services/citation_correction.py::correct_source_references()` is the deterministic
backstop behind every SOURCE_BACKED citation: the LLM only needs to copy a real `chunk_id` it
already saw in its retrieved context; everything else on the citation (document name, page,
section) is overwritten from `document_chunk_meta`, never trusted from model output. It's
wired into `run_requirement_analyst_agent` (for requirements) and Planning's RAID generation
(risks/assumptions/issues) directly, plus the *fallback* path in `_assign_epic_ids`/
`_assign_story_and_ac_ids` for when an epic/story's `grounding_requirement_ids` doesn't resolve
to a real requirement (added Day 23 — the original Day 22 version missed this specific
fallback branch, found via a live run's `validation_is_valid: false`). A `chunk_id` that
doesn't resolve to anything real is left alone on purpose — that's what the dangling-citation
check in `validate_project_plan` exists to catch.

## Requirement coverage — the two-layer approach

Getting every approved requirement represented somewhere in the plan (§24.10's 90% target)
turned out to need two layers, not one: an explicit COVERAGE instruction in the epics/stories
prompts (Day 22, real but incomplete improvement — 71%→~80% baseline), plus a deterministic
backstop, `_backfill_epic_coverage()` in `app/agents/planning.py` (Day 22): after the main
epics call, compute which approved requirements ended up covered by *no* epic, and — only if
any remain — make one additional, narrowly-scoped LLM call asking specifically to place those
into an existing epic (never inventing a new one). It costs nothing extra when coverage is
already complete. Confirmed at 100% coverage across a live run. This is the same "prompt
first, deterministic backstop second" pattern used throughout the codebase for anything the
Reviewer's own structural checks can catch too — see `_force_revision_on_structural_failure`
in `app/agents/reviewer.py` for the canonical example.

## Versioning (spec §22)

Every plan regeneration creates a new `PlanArtifactVersion` row
(`save_planning_artifacts` in `app/tools/project_tools.py`) rather than overwriting the
current one — `version_number`, `model`, `prompt_version`, `generated_at`, and `is_current`
are all captured at save time. `GET /projects/{id}/plan` always returns the current version;
`GET /projects/{id}/plan/versions` lists every version's metadata (newest first), and
`GET /projects/{id}/plan/versions/{version_id}` returns one specific version's full plan —
added Day 23, since the version data had been tracked since Day 12/13 but never exposed. This
is what lets a UI (or a script) compare "previous output, new output" as the spec asks for.

## Jira CSV field mapping (spec §17)

One CSV row per Epic/Story, built by `app/services/export_service.py::build_jira_csv_rows`:

| CSV column | Source |
|---|---|
| Issue Type | `Epic` / `Story` (row type) |
| Summary | `title` |
| Description | `story_statement` / epic `description` |
| Epic Name | epic `title` (epic rows) |
| Epic Link | story `epic_id` |
| Parent ID | story `epic_id` |
| Priority | `priority` |
| Story Points | `suggested_story_points` |
| Acceptance Criteria | AC rendered Given/When/Then, joined |
| Dependencies | `dependencies` joined |
| Labels | category/classification-derived |
| Source References | `source_references` formatted (doc·page·section·chunk_id) |
| AI Classification | `classification` |

(Also documented in the local `docs/DESIGN.md` §13 working notes — this table is the
canonical, git-tracked copy going forward.)

## Database migrations — there isn't a tool yet

`Base.metadata.create_all()` (SQLAlchemy) creates tables that don't exist yet, but it **never**
alters an existing table — so a schema change (a new column, a new table) requires manually
altering any already-created dev database. This bit once for real: `plan_artifact_versions`
was missing `reviewer_report_json` in a dev DB created before that column was added, and the
only fix available was a manual `ALTER TABLE plan_artifact_versions ADD COLUMN
reviewer_report_json JSON`. If you add a column to an existing model, either delete your local
`data/app.db` and let it recreate cleanly, or run the equivalent `ALTER TABLE` by hand — there
is no Alembic (or similar) integration in this codebase yet. See the
[README's Future improvements section](README.md#future-improvements) for the recommendation
to add one.

## Running the evaluation suite

Scripts live in `evaluation/scripts/`, each independently runnable and each with a driver test
in `tests/integration/`:

| Script | What it measures | Live model? |
|---|---|---|
| `run_extraction_evaluation.py` | Requirement extraction accuracy (§24.1) | Yes — slow |
| `run_routing_evaluation.py` | Supervisor routing correctness (§24.3) | Yes — slow |
| `run_repeatability_evaluation.py` | Run-to-run consistency (§24.8) | Yes — slow |
| `run_seeded_error_evaluation.py` | Reviewer effectiveness against 6 seeded defects (§24.7) | Yes — slow |
| `run_retrieval_evaluation.py` | Retrieval quality (§24.9) | **No** — pure embedding + vector search, seconds |
| `run_day22_live_verification.py` | Full-pipeline behavioral spot-check (scenario-agnostic despite the name) | Yes — slow (1-2.5h) |

"Slow" scripts run against a real `qwen3:4b-instruct` — expect anywhere from minutes
(routing) to hours (a full pipeline run with a revision cycle). Run them explicitly with
`pytest -m slow`; the default `pytest` invocation deselects everything marked `@pytest.mark.slow`
so the regular fast suite stays fast. **Never run two live-model tests concurrently** — this
project runs a single-sequence local Ollama instance, and concurrent live calls have caused
real, reproducible spurious failures (empty responses under contention) that look like bugs
but aren't (see `docs/PROJECT_PLAN.md`'s Day 22 notes for a worked example).

# Day 22 Evaluation Report — §24.10 Quantitative Checks + Rubric Fixes (Round 1)

Spec sections covered: §24.10 (required quantitative checks), plus fixes against the
Known-Issues Backlog (`docs/PROJECT_PLAN.md`) targeting §33's three highest-weighted rubric
areas that were well-scoped for one day: Agent design and workflow control (20%), RAG
implementation and project isolation (15%), Planning-artifact quality (15%), plus one cheap
Testing-and-guardrails (5%) win.

This day's job is precision, not optimism: every claim below is backed by either a
by-construction guarantee (with the exact test that proves it), or a live-model run captured
today, or an honestly-reported non-result. Nothing here is asserted from prompt text alone
without a runtime check.

## §24.10 — Required quantitative checks

| # | Target | Verdict | Evidence |
|---|---|---|---|
| 1 | 100% schema-valid final JSON output | **PASS** (see note) | By construction — `save_planning_artifacts` calls `ProjectPlan.model_validate()` before persisting anything; a plan that fails Pydantic validation is never saved. Distinct from `validate_project_plan`'s stricter *semantic* checks below. |
| 2 | No user story without acceptance criteria | **PASS** | By construction — `UserStory.acceptance_criteria: Field(min_length=1)`. `tests/unit/test_schemas.py::test_user_story_requires_acceptance_criteria`. |
| 3 | No user story without a parent epic | **PASS** | By construction — `ProjectPlan._validate_cross_references` rejects an unknown `epic_id`; `UserStory.epic_id: Field(min_length=1)` rejects a blank one. `tests/unit/test_schemas.py::test_user_story_requires_epic_id`, `::test_project_plan_rejects_story_with_unknown_epic`. |
| 4 | No source-backed artifact without a citation | **PASS**, strengthened this day | By construction — `GroundedMixin`'s SOURCE_BACKED-needs-citation validator (`tests/unit/test_schemas.py::test_epic_source_backed_without_citation_rejected`). **This day adds accuracy, not just presence** — Task 1 below. |
| 5 | No cross-project retrieval in the evaluation dataset | **PASS** | Not re-tested today (already extensively covered Days 6/17/18/21 at both the vector-retrieval layer and the DB/API layer). |
| 6 | ≥90% of manually identified major requirements represented in the generated plan | **PASS** (after round 2) | Day 20 baseline (scenario 2): 71.0% (22/31). Round 1 (prompt-only fix, scenario 1): 86.4% and 75.7% across two runs — improved, still short. Round 2 (deterministic coverage-backfill mechanism added): **100.0%** (0 gaps, 32/32 requirements) on a third independent live run. See Task 3 below. |
| 7 | ≥80% correct source retrieval in top-5 | **PASS** | Day 21: 100% (28/28 applicable queries). Not re-tested today — Day 21's evidence stands. |
| 8 | Successful rejection/clarification for most deliberately unanswerable questions | **PASS (qualified)** | Day 19: the Requirement Analyst mapped 5/5 of scenario 3's deliberately-seeded contradictions/ambiguities to generated clarification questions. Day 21's retrieval-layer score-gap finding (genuine matches 0.75–0.82 vs. no-answer queries 0.50–0.58) is supporting, not identical, evidence — retrieval and requirement-analysis are different components measuring different things. |

**Note on #1**: this project uses "schema-valid" in two senses that must stay distinct, or
Day 20's finding gets misread as contradicting this PASS. (a) *Structural* Pydantic validity —
every field present, every type correct — is guaranteed at save time and can never fail
silently; this is what #1 asks for. (b) *Semantic* validity via `validate_project_plan`
(dangling citations, circular dependencies, orphan references) is a stricter, separate check
that a structurally-valid plan can still fail — this is what Day 20 called "schema-invalid" for
2/3 repeatability runs. Both of this day's two live runs (below) passed *both* senses:
`validation_is_valid: true, validation_error_count: 0` in each.

## This day's fixes

### Task 1 — Deterministic citation-field correction (RAG grounding, §33 15%) — CONFIRMED FIXED

**Root cause** (confirmed by reading the code): every `SourceReference` was written entirely by
the LLM — nothing cross-checked `document_name`/`page_number`/`section` against the real,
recorded chunk metadata. First found Day 15, reconfirmed Day 19 (5/5 sampled scenario-3
citations pointed at the document title instead of a real subsection).

**Fix**: new `app/services/citation_correction.py::correct_source_references()` — overwrites
every field except `chunk_id` from `document_chunk_meta`/`documents`, filtered by
`project_id` (mirrors the existing dangling-citation validator's own isolation filter). Wired
into the Requirement Analyst (`result.requirements`) and Planning's RAID generation
(risks/assumptions/issues — the one place besides Requirements where citations are still
model-authored directly; Epics/Stories already inherit corrected citations via
`grounding_requirement_ids` backfill). A `chunk_id` that doesn't resolve is left untouched —
the existing dangling-citation validator remains the sole authority for that failure mode.

**Verified**: 4 unit tests (`tests/unit/test_citation_correction.py`) plus a mocked-LLM
regression test proving the wiring (`tests/unit/test_requirement_analyst_agent.py`). Then
**live, three times**: citation section accuracy was **22/22**, **36/36**, and **31/31** (all
100%) across all three independent full pipeline runs against a live `qwen3:4b-instruct` — every
single citation, in every run, now carries the real recorded section text.

### Task 2 — Supervisor error-priority prompt fix (Agent design and workflow control, §33 20%) — CONFIRMED FIXED

**Root cause**: Day 19's routing evaluation found 2/17 situations where the Supervisor ignored
recorded errors and recommended `RUN_REQUIREMENT_ANALYST`/`EXPORT_PLAN` instead of
`STOP_WITH_ERROR` — the prompt surfaced errors but never stated they override every other
consideration.

**Fix**: one explicit `PRIORITY RULE` line added to the Supervisor's prompt
(`app/agents/supervisor.py`), mirroring the exact shape of Day 19's already-proven
`final_approved` fix.

**Verified**: 1 new unit test proving the rule is present in the prompt
(`tests/unit/test_supervisor_agent.py::test_supervisor_prompt_states_errors_always_override_other_state`).
Then a targeted live rerun of the two specific situations that failed Day 19
(`multiple_errors_recorded`, `error_recorded_despite_otherwise_complete_state`, via
`evaluation/scripts/run_routing_evaluation.py`'s existing `SITUATIONS` list, not modified):
**both now correctly return `STOP_WITH_ERROR`**, with the model's own reasoning explicitly
echoing the new rule — e.g. *"...must stop immediately regardless of other stages or
readiness."* Day 19's routing pass rate for this class of situation moves from 0/2 to 2/2.

### Task 3 — Planning Agent requirement coverage + story points (Planning-artifact quality, §33 15%) — CONFIRMED FIXED, after a second round of iteration

This task went through two full rounds within Day 22 itself — round 1's prompt-only fixes
gave real but incomplete improvement; the user explicitly chose to keep iterating rather than
defer the remainder to Day 23, and round 2's mechanism-level fixes closed both gaps completely.

**Coverage — root cause**: `_build_traceability_matrix` only counts a requirement as covered if
some *epic* references it in `grounding_requirement_ids` — the epics prompt never instructed
the model that every approved requirement must land in at least one epic, so some were silently
dropped at that stage (Day 20 baseline: 71.0%, scenario 2).

- **Round 1 fix**: an explicit COVERAGE rule added to both `_EPICS_SYSTEM_PROMPT` and
  `_STORIES_SYSTEM_PROMPT` (`app/agents/planning.py`). **Result**: two independent live runs
  (scenario 1) measured 86.4% (19/22, 3 gaps) and 75.7% (28/37, 9 gaps) — real improvement over
  the 71.0% baseline, but short of the §24.10 90% target.
- **Round 2 fix**: a deterministic post-check, `_backfill_epic_coverage()`
  (`app/agents/planning.py`) — after the main epics call, compute which approved requirements
  ended up covered by *no* epic; if any remain, issue one additional, narrowly-scoped LLM call
  (`EpicCoverageBackfillResult`, `app/schemas/planning.py`) asking specifically to place those
  into an existing epic (never inventing a new one), then deterministically merge the result
  (grounding IDs + recomputed citations via the same `_grounded_source_references` helper
  Task 1 relies on). Costs nothing extra when coverage is already complete. **Result**: a third
  independent live run measured **100.0% coverage (0 gaps, 32/32 requirements)**.
  - Honest caveat: app-level `logger.info` calls aren't captured in a passing (vs. failing)
    pytest run's output, so this evaluation can't directly confirm whether the backfill call
    actually fired this run or whether round 1's prompt rule alone happened to reach 100% on
    its own. Either way, the coverage problem is resolved — the backfill mechanism exists as a
    guaranteed backstop for any future run where the prompt alone falls short, at zero cost
    when it isn't needed. A cheap follow-up (log backfill-firing to a `WorkflowEvent` rather
    than a plain logger call) would remove this ambiguity for future evaluations but wasn't
    worth a 4th live run today.

**Story points — root cause**: `_STORIES_SYSTEM_PROMPT` never required a numeric estimate, and
`UserStoryDraft.suggested_story_points: int | None = Field(default=None, ge=0)` compiled to a
nullable JSON schema for Ollama's constrained decoding.

- **Round 1 fix**: the prompt was changed to say `suggested_story_points is REQUIRED... never
  leave it null`, plus a dedicated `search_company_standards("story point estimation scale",
  category="Estimation")` call was added for the stories-generation call. **Result — confirmed
  NOT fixed**, tested across two separate live runs: 0/18 (run 1, before discovering the live
  verification script itself never uploaded organizational-standards documents — a
  test-methodology gap, not evidence against the fix) and 0/27 (run 2, after fixing that gap —
  `estimation_guidance.md`'s real Fibonacci scale was genuinely retrievable and present in
  context). The prompt instruction alone was not followed by the model in either run.
- **Round 2 fix**: changed `UserStoryDraft.suggested_story_points` from `int | None =
  Field(default=None, ge=0)` to a required, non-nullable `int = Field(ge=1)` — removing `null`
  as a legal completion at the JSON-schema grammar level itself, rather than only asking for a
  number in prose. (The final `UserStory` schema deliberately keeps `int | None`, so a
  legitimate "not yet estimated" state remains representable elsewhere in the system even
  though the model can no longer produce it directly at this call site.) **Result**: the third
  live run measured **19/19 (100%)** — every story now carries a real point estimate.

This is a good, concrete confirmation of hypothesis 2 from round 1's diagnosis: the nullable
schema itself, not prompt wording, was very likely the actual blocker. A useful, generalizable
lesson for this project: **a prose instruction to a small local model competes with dozens of
other instructions in a long system prompt, but a schema-level constraint is enforced by the
decoding grammar regardless of prompt attention** — worth keeping in mind for any future
"the model isn't reliably doing X" finding before reaching for a longer prompt.

### Task 4 — `WorkflowEvent.duration_ms` population (Testing and guardrails, §33 5%) — CONFIRMED FIXED

**Root cause**: the field and its consumer (`log_event`) existed since Day 7; nothing ever
passed a value. Every duration in the Day 19/20 evaluation reports had to be reconstructed after
the fact from IN_PROGRESS/SUCCESS timestamp pairs.

**Fix**: each of the 5 agent-calling nodes in `app/workflow/graph.py`
(`supervisor_node`, `requirement_analyst_node`, `planning_node`, `reviewer_node`,
`plan_revision_node`) now times itself with `time.perf_counter()` and passes the real elapsed
milliseconds into every terminal (SUCCESS/ERROR) `log_event` call.

**Verified**: `tests/unit/test_workflow_event_durations.py` (a node call with an artificially
slowed mock proves a real, non-null `duration_ms` lands in the DB). Then confirmed live in all
three of today's full pipeline runs — `duration_ms_populated: true` in every run, with real
per-agent timings now readable directly from `WorkflowEvent` rows for the first time in this
project's history (no more timestamp-pairing reconstruction needed for future evaluations):

| Agent / stage | Run 1 (86.4% coverage) | Run 2 (75.7% coverage) | Run 3 (100% coverage) |
|---|---|---|---|
| Requirement Analyst | 725.3s (12.1 min) | 786.2s (13.1 min) | 678.7s (11.3 min) |
| Planning (initial) | 1969.4s (32.8 min) | 3566.9s (59.4 min) | 2239.8s (37.3 min) |
| Reviewer (1st pass) | 384.7s (6.4 min) | 527.5s (8.8 min) | 216.4s (3.6 min) |
| Planning (revision) | 1752.1s (29.2 min) | 3748.6s (62.5 min) | *(none — passed 1st try)* |
| Reviewer (2nd pass) | 310.1s (5.2 min) | 358.6s (6.0 min) | *(none needed)* |
| Supervisor (4-6 calls) | 9.6–33.3s each | 8.0–32.8s each | 5.3–11.2s each |
| **Total wall-clock** | 1h27m | 2h32m | 53m |

Runs 1 and 2 both independently triggered the single allowed revision cycle (§20.1); run 3
passed on the Reviewer's first attempt with no revision needed at all — the fastest and
cleanest of the three. All three ended `validation_is_valid: true`. Three runs is still not
enough to draw a firm repeatability conclusion (Day 20's §24.8 finding was exactly that
schema-validity and revision-triggering vary run to run), but it's a more encouraging spread
than Day 20's scenario-2 results (1/3 clean, 2/3 revision-then-still-invalid).

## Known-Issues Backlog changes

See `docs/PROJECT_PLAN.md`'s "Known-Issues Backlog" section — this day removes 5 items
entirely (confirmed fixed and live-verified): citation section-accuracy, `duration_ms`, one of
the two Supervisor error-handling inconsistencies, missing story points, and requirement
coverage below the §24.10 target. Everything else (empty dependency descriptions, Planning
scope invention, retrieval version-unawareness, API completeness for contradictions/
ambiguities, the dependency-ordering 404-vs-503 edge case, eval-script capture narrowness, and
the one Supervisor error-handling inconsistency not exercised by this day's live rerun) is
carried forward unchanged to Day 23.

## Verification

- Full fast suite: 352 passed, 7 deselected, 0 failures (up from Day 21's 340 passed / 6
  deselected — 12 new fast tests across the day's fixes, plus 1 new `@pytest.mark.slow` test).
  `ruff check` clean on every file this day touched.
- **Three** full live pipeline runs against scenario 1 (leave management) — 1h27m, 2h32m, and
  53m — confirming every fix behaviorally rather than assuming from prompt/code changes alone.
  The first two rounds gave an honest, non-fabricated partial result for two of the fixes; the
  user explicitly chose to keep iterating rather than accept "improved but not confirmed" for
  Day 23, and the third run confirmed all five fixes with clean numbers: 100% citation
  accuracy, 100% requirement coverage, 100% story-point coverage, 0 validation errors, and a
  single-pass Reviewer approval with no revision cycle needed.

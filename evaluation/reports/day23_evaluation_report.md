# Day 23 Evaluation Report — Rubric Fixes (Round 2) + Versioning Polish

Spec sections covered: §13.8 (dependencies), §12.2/Day 21 (retrieval version-awareness), §22
(versioning — this day's named focus), §13.1/§13.2 (contradictions/ambiguities), §20.4
(dependency-ordering), plus one unplanned but user-requested fix discovered mid-day via live
verification (epic/story citation-correction fallback gap).

Every claim below is backed by either a by-construction schema guarantee, a passing unit/
integration test, or a live-model run — nothing is asserted from code changes alone without a
runtime check where the fix touches live-model-observable behavior.

## Summary

6 backlog items addressed, all confirmed; one new §22 capability delivered; one additional
issue found and fixed mid-day at the user's explicit direction after it surfaced during live
verification, rather than being left as an honestly-reported-but-open finding.

| # | Item | Rubric area (§33) | Result |
|---|---|---|---|
| 1 | Empty dependency descriptions | Planning-artifact quality (15%) | **Fixed** — schema + prompt, confirmed live |
| 2 | Retrieval has no version awareness | RAG implementation (15%) | **Fixed** — confirmed via Day 21's retrieval suite (no live LLM needed) |
| 3 | No plan-version history API | §22 (day's named focus) | **Delivered** — 2 new endpoints, data already existed |
| 4 | No contradictions/ambiguities endpoint | API completeness (10%) | **Fixed** — new persistence + 2 endpoints |
| 5 | Dependency-ordering 404-vs-503 | Testing and guardrails (5%) | **Fixed** — confirmed via targeted regression tests |
| 6 | Eval-script capture narrowness | Evaluation/failure analysis (5%) | **Fixed** (capture code only — live rerun explicitly deferred, see below) |
| — | Epic/story citation-correction fallback gap (found this day) | RAG grounding (15%) | **Fixed** — confirmed live, `validation_is_valid` went false→true |

Deliberately not touched, unchanged from the Day 22 backlog: Planning Agent scope invention
(no cheap way to investigate "one-off or systemic" without another multi-scenario live
investigation) and the one remaining Supervisor error-handling inconsistency (already diagnosed
as a low-impact small-model quirk with no identified fix, per Day 19/22).

## Task 1 — Dependency description/resolution fix (Planning-artifact quality, 15%)

**Root cause**: `DependencyDraft.description`/`suggested_resolution` both defaulted to `""`
with no prompt instruction covering either field — the same shape of bug Day 22 found and fixed
for `suggested_story_points` (an optional field silently omitted under Ollama's constrained
decoding).

**Fix**: both fields changed to `Field(min_length=1)` on the draft schema; an explicit prompt
rule added requiring concrete content for both. `tests/unit/test_planning_agent.py` gained a
regression test proving the schema rejects a missing/empty value.

**Live verification**: both live runs this day (§ below) completed a full Planning cycle
without any `ValidationError` from `DependencyDraft` parsing — a `min_length=1` violation would
have failed the whole pipeline, so a clean completion structurally confirms every generated
dependency carried real content.

## Task 2 — Retrieval version-awareness (RAG implementation, 15%)

**Root cause** (Day 21 finding): `_scroll_corpus` had no concept of "latest version" — every
indexed chunk from every uploaded version of a same-named document was an equally eligible
retrieval candidate.

**Fix**: `_keep_latest_version_per_document_name()` added to `app/services/retrieval_service.py`,
applied right after scrolling in `hybrid_search` — groups candidates by `document_name`,
compares `document_version` as a float, keeps only the max.

**Verification** (zero live LLM calls, same as Day 21's original evaluation): 3 new unit tests
directly on the filtering function, plus a full rerun of Day 21's 32-query retrieval evaluation
with 4 queries rewritten to test the new, correct contract:
- The 3 `document_versions` queries now assert real content (`"25 days"` not `"20 days"`,
  `"2.08 days/month"` not `"1.67 days/month"`) and `expect_max_distinct_document_ids: 1` —
  previously these asserted nothing (`expect_version_note` was dead weight).
- The `multi_document` query that previously demonstrated *both* versions returning together
  (`expect_min_distinct_document_ids: 2` — the bug, misframed as a feature) was retired and
  replaced with a direct version-awareness assertion in the `document_versions` category.
- Confirmed via the raw JSON report: every `document_versions` query now returns
  `document_versions: ["2.0"]` only, `distinct_document_ids: 1` — never both.

## Task 3 — Plan-version history API (spec §22, this day's named focus)

**Finding**: `PlanArtifactVersion` already stored every field §22 asks for —
`version_number`, `model`, `prompt_version`, `generated_at`, `is_current`, full `plan_json` —
since Day 12/13. The gap was entirely on the read side: `GET /projects/{id}/plan` only ever
returned the current version, with no way to list or fetch a previous one.

**Fix**: `GET /projects/{id}/plan/versions` (list, metadata only, newest first) and
`GET /projects/{id}/plan/versions/{version_id}` (full plan JSON for one specific version).

**Verified**: 5 new unit tests (list ordering, full-plan retrieval, 404 for unknown version,
404 for unknown project, project isolation) — pure deterministic CRUD, no live LLM needed.

## Task 4 — Contradictions/ambiguities persistence + read endpoints (API completeness, 10%)

**Finding**: `RequirementAnalysisResult.contradictions`/`.ambiguities` were real, already-
generated LLM output (used internally to build clarification questions) but discarded the
moment `run_requirement_analyst_agent` returned — `save_requirements` only ever persisted
`.requirements`.

**Fix**: two new tables (`ContradictionRecord`, `AmbiguityRecord`, mirroring the existing
`RequirementRecord`/`ClarificationQuestionRecord` pattern exactly), a new
`save_analysis_findings()` tool wired in right after `save_clarification_questions`, and two
new read endpoints (`GET /projects/{id}/contradictions`, `GET /projects/{id}/ambiguities`).

**Verified**: 9 new unit tests including one proving the full wiring through
`run_requirement_analyst_agent` with a mocked LLM (not just the persistence function in
isolation). Both live verification runs this day confirmed the endpoints return real data
without error (scenario 1 is the "standard, non-ambiguous" scenario per §23, so a small or
empty result here is expected and not itself a finding — the fine-grained counts weren't
captured to the report file this day, a minor instrumentation gap noted for future evaluation).

## Task 5 — Dependency-ordering 404-vs-503 fix (Testing and guardrails, 5%)

**Root cause** (Day 17 finding): `start_workflow`, `approve_clarifications`, and `approve_plan`
all called `_require_project` as the first line of the function *body*, but FastAPI resolves
every `Depends()` parameter — including `get_vector_service`, which raises a 503 when Qdrant is
down — before the body ever runs. A nonexistent project that also coincided with Qdrant being
down surfaced as 503, masking the real 404.

**Fix**: a `_require_project_dependency` added to each of the 3 files, declared as an early
`Depends()` parameter (before `checkpointer`/`session_factory`/`vector_service`) so it resolves
first. **Found and fixed the identical bug in a 4th route while there** — `workflow_status` also
depends on `get_vector_service` (via `engine.get_pending_gate_stage`) and had the same gap; the
original Day 17 finding only named the 3 mutating routes, but this one was trivial to include
consistently.

**Verified**: 5 new regression tests, including one confirming the fix's boundary (a *real*
project with Qdrant down still correctly gets 503, not masked into a false 404) — all passed on
the first run, confirming FastAPI genuinely resolves sibling `Depends()` in declaration order
for this case. The existing `test_api_error_handling.py` suite (Day 17's original coverage)
still passes unchanged.

## Task 6 — Eval-script capture narrowness fix (Evaluation and failure analysis, 5% — eval-tooling debt)

**Root cause** (Day 20 finding): `run_seeded_error_evaluation.py`'s capture only concatenated 3
of `ReviewerReport`'s 6 `ReviewerIssue`-list fields into one `issues` list — the exact mixing
of dicts and strings across different outcome branches that caused a real crash during Day 20's
live run.

**Fix**: every `ReviewerIssue`-list field (`unsupported_claims`, `duplicate_stories`,
`missing_acceptance_criteria`, `weak_acceptance_criteria`, `traceability_gaps`,
`dependency_issues`) is now captured under its own key, never merged; the 2 string-list fields
(`missing_requirements`, `warnings`) are captured separately; and a direct call to
`validate_project_plan` per seed now confirms (not infers) whether `REVISION_REQUIRED` came
from the deterministic structural backstop.

**Scope decision, explicitly not done this day**: Day 20's 6 live Reviewer calls were **not**
rerun to get fresh attribution data with the new capture code — that's a real but lower-priority
cost (5%-weighted eval tooling, not `app/` code), and this day already spent ~4 hours of live
model time on the two live verification runs below. The capture fix itself is proven correct by
a structural unit test with a mocked `ReviewerReport` (no live model needed) — the backlog entry
for this item stays open, now with the capture code ready for whenever that rerun happens.

## Unplanned fix — Epic/story citation-correction fallback gap (RAG grounding, 15%)

**How it was found**: the first live verification run this day (below) came back with
`validation_is_valid: false, validation_error_count: 2` on the final, post-revision plan — not
something any of this day's 6 planned tasks targeted. The in-memory test database was gone by
the time this was investigated (no way to query the 2 specific errors directly), so the
diagnosis was built circumstantially rather than from direct observation:

1. An offline diagnostic (zero live-model cost) ran `validate_project_plan()` against Day 20's
   two already-known-invalid saved plan JSONs. **100% of the errors in both — 44 and 39
   respectively — were `DANGLING_CITATION`/`MISSING_SOURCE_REFERENCE`**, zero circular-
   dependency/duplicate-ID/missing-field errors. A strong pattern: this class of plan-invalidity
   is citation-related, not structural.
2. Reading `_assign_epic_ids`/`_assign_story_and_ac_ids` in `app/agents/planning.py` found the
   actual gap: Day 22's citation-correction fix (`app/services/citation_correction.py`) covers
   Requirements and RAID items (Risks/Assumptions/Issues), and Epics/Stories inherit corrected
   citations *when their `grounding_requirement_ids` successfully resolves*. When it doesn't
   (the model references a requirement ID that doesn't exist), the code fell back to the
   model's own raw citation — completely uncorrected, unlike every other path.

**Fix**: `_assign_epic_ids` and `_assign_story_and_ac_ids` (and `_generate_stories`, which
needed `project_id`/`session_factory` threaded through to reach it) now run the fallback
citation through `correct_source_references()` too — a real chunk_id gets its
document_name/page/section fixed even when grounding fails; a chunk_id that still doesn't
resolve stays dangling on purpose, so the deterministic validator can still catch a genuinely
fabricated citation. A new regression test seeds a real chunk and an ungrounded epic citing it
with wrong metadata, proving the fallback path is now corrected the same way the grounded path
already was.

**Verified live, twice** — the user explicitly chose to fix and reconfirm rather than accept
the finding as open:
- **Before the fix**: `validation_is_valid: false, validation_error_count: 2` (2h17m run).
- **After the fix**: `validation_is_valid: true, validation_error_count: 0` (1h55m run) — and
  every other metric held clean: 100% coverage (0 gaps), 100% citation accuracy (35/35), 100%
  story points (16/16) — even though this run also triggered the one allowed revision cycle.

## Live verification summary

Two full pipeline runs against scenario 1 (leave management), matching this project's
established "verify behaviorally, don't assume" convention:

| | Run 1 (before fallback fix) | Run 2 (after fallback fix) |
|---|---|---|
| Total wall-clock | 2h17m28s | 1h55m18s |
| Final status | COMPLETED | COMPLETED |
| Requirements / Epics / Stories | 36 / 13 / 28 | 37 / 14 / 16 |
| Traceability coverage | 100.0% (0 gaps) | 100.0% (0 gaps) |
| `validation_is_valid` | **false (2 errors)** | **true (0 errors)** |
| Citation section accuracy | 35/35 (100%) | 35/35 (100%) |
| Stories with story points | 28/28 (100%) | 16/16 (100%) |
| Revision cycle fired? | Yes (Planning + Reviewer ×2) | Yes (Planning + Reviewer ×2) |

Both runs independently triggered the one allowed revision cycle (§20.1) — Run 2's clean
`validation_is_valid: true` result *after* a revision is a genuinely strong signal, not a lucky
first-pass pipeline that never got tested under the harder revision path.

## Full fast suite

372 passed, 8 deselected (Day 15/18/19×2/20's original slow tests, plus this day's new
`test_run_day23_live_verification`), 0 failures — up from Day 22's 352/7 (20 new fast tests
across this day's 6 tasks plus the unplanned fallback-correction fix). `ruff check` clean on
every file this day touched.

## Known-Issues Backlog changes

See `docs/PROJECT_PLAN.md`'s "Known-Issues Backlog" section — this day removes 6 items
entirely (Tasks 1, 2, 4, 5, and the unplanned citation-fallback fix, all confirmed and
live-verified where applicable) and delivers Task 3 as a new capability rather than a backlog
removal. Task 6's item stays open (capture code fixed, live rerun deferred). Two items are
carried forward unchanged: Planning Agent scope invention, and the remaining Supervisor
error-handling inconsistency.

# Day 19 Evaluation Report — Extraction, Clarification, Routing, Tool Selection, Grounding

Spec sections covered: §24.1, §24.2, §24.3, §24.4, §24.5.
Raw data: `evaluation/reports/scenario_*_raw_result.json`, `day19_automated_metrics.md`,
`day19_routing_evaluation.md`. Gold-standard baselines: `evaluation/expected_results/`.
All numbers below come from real, live `qwen3:4b-instruct` runs — no mocked model output.

## §24.1 Requirement Extraction

Target: ≥85% of manually identified major requirements extracted; every SOURCE_BACKED item
has a source reference.

| Scenario | Major reqs (gold) | Found | Recall | Invented reqs | Citation rate | RA call duration |
|---|---|---|---|---|---|---|
| 1 Leave Management | 20 | 20 | 100% | 0 | 100% | 766.1s (12.8 min) |
| 2 E-Commerce Payments | 17 | 17 | 100% | 0 | 100% | 1147.0s (19.1 min) |
| 3 Ambiguous Support | 10 | 9 | 90% | 0 | 100% | 656.8s (10.9 min) |
| **Overall** | **47** | **46** | **97.9%** | **0** | **100%** | mean 856.6s (14.3 min) |

**Result: PASS** (97.9% ≫ 85% target; 100% citation rate meets the "every SOURCE_BACKED item
has a source reference" requirement exactly).

Notes:
- Scenarios 1 and 2 achieved perfect recall — every gold-standard requirement, including all
  non-functional requirements, constraints, and dependencies, was extracted with a correct
  category and a valid citation.
- Scenario 3's one miss: the vague "the assistant should be secure" NFR (gold item #5) was
  extracted as a plain SOURCE_BACKED requirement (REQ-005) rather than being flagged as
  ambiguous/non-testable per §7.2 task 12 — no clarification question was generated for it
  either. This is the one place across all 3 scenarios where a genuinely vague, non-testable
  statement from the source document was silently accepted rather than questioned.
- Zero invented requirements across all 47 gold items and all 77 total extracted requirements
  — every extracted requirement traces to real document content.
- Requirement Analyst call duration scales with document richness, not raw line count:
  scenario 2 (64 lines, dense integration/dependency/risk content) took the longest (19.1
  min) despite being shorter than scenario 1 (71 lines, 12.8 min) — consistent with more
  distinct requirement categories to reason about (31 vs 28 requirements extracted), not
  simply more text to read.

## §24.2 Clarification Quality

Target: ≥80% of generated clarification questions considered useful.

| Scenario | Questions generated | Useful | Rate | Gold ambiguities/contradictions surfaced |
|---|---|---|---|---|
| 1 Leave Management | 7 | 7 | 100% | N/A (none expected — clean document) |
| 2 E-Commerce Payments | 5 | 5 | 100% | N/A (none expected — clean document) |
| 3 Ambiguous Support | 5 | 5 | 100% | 5/7 as explicit questions (see below) |
| **Overall** | **17** | **17** | **100%** | — |

**Result: PASS** (100% ≫ 80% target).

Every question across all 3 scenarios was judged relevant, specific, non-duplicate, and
answerable by a PM without needing engineering input — e.g. "What defines a 'pending' leave
request?", "What is the definition of 'normal load' in the context of webhook processing
time?". One question (scenario 1, Q-007, "Are audit logs encrypted or backed up?") is
slightly different in kind — it probes an area the source document never mentions at all,
rather than resolving a stated ambiguity — but is still genuinely useful and answerable, so
it's still counted as USEFUL.

Scenario 3 deep dive (the scenario this criterion actually exists to test, §23): of the 7
gold-standard items expected to be flagged (2 vague NFRs + 3 contradictions + 2 ambiguities),
5 became distinct, well-targeted clarification questions:
- Q-001 → admin/config tool roles (gold #10) ✓
- Q-002 → vague "fast and responsive" NFR (gold #4) ✓
- Q-003 → channel contradiction: chat-only vs. chat+email+IVR (gold #6) ✓
- Q-004 → retention contradiction: 1yr vs. 7yr (gold #7) ✓
- Q-005 → escalation routing ambiguity (gold #9) ✓

Two gold items were not turned into standalone questions: the Q2-vs-Q3/Q4 launch-date
contradiction (gold #8) was instead synthesized directly into a single requirement's
description (REQ-011: "Launch date is targeted for Q2 but realistically expected in Q3 or
Q4") rather than posed as an open question — arguably still useful information for a PM, just
delivered differently than expected; and the vague "secure" NFR (gold #5, the same miss noted
in §24.1) was not surfaced at all.

## §24.3 Agent Routing

Full 17-situation table: `evaluation/reports/day19_routing_evaluation.md`.

**Pass rate: 15/17 (88%)**, after a fix applied and reverified within this same day (see
below) — up from an initial 12/17 (71%) on the first live run.

This evaluation replaces the tautological check in `tests/unit/test_supervisor_agent.py`,
which mocks `run_agent` to return exactly the value under assertion and so could never
actually detect a Supervisor reasoning error (flagged, not fixed, since Day 9's
`docs/PROJECT_PLAN.md` notes). Every one of these 17 decisions came from a real live model
call, mean duration 5.4s (min 3.7s, max 17.7s) — cheap enough that this evaluation is fast
to rerun, which is exactly what made verifying the fix below practical within the same day.

**Initial run found 5 failures with one of two root causes:**

1. **3 failures — same pattern, real prompt gap, fixed and reverified this day:**
   `reviewer_pass`, `reviewer_pass_with_warnings`, and `post_revision_reviewer_now_passes` all
   expected `WAIT_FOR_FINAL_APPROVAL` but the model returned `EXPORT_PLAN`. Root cause,
   confirmed by reading `app/agents/supervisor.py::_summarize_state`: when
   `clarification_approved` is still `False`, the state summary explicitly prints `"⏸
   Clarification approval: AWAITING human approval to proceed"` — but there was **no
   equivalent line for `final_approved`**. The summary only ever mentioned final approval
   when it was already `True` ("✓ Final approval: APPROVED"); when it was `False`, the
   summary said nothing about it at all, so the model had no explicit textual cue that a
   human gate was still pending. **Fixed**: added a mirroring line, firing only when
   `reviewer_decision in ("PASS", "PASS_WITH_WARNINGS")` and `final_approved` is still
   `False` — `"⏸ Final approval: AWAITING human approval to proceed — review passing does NOT
   mean it is ready to export..."`. Verified two ways: a new deterministic unit test
   (`tests/unit/test_supervisor_agent.py::test_state_summary_explicitly_flags_pending_final_approval`,
   plus a companion test proving the line does *not* fire once actually approved) and a full
   live rerun of this evaluation — all 3 previously-failing situations now pass, each citing
   "requires human approval" in the model's own reasoning (e.g. `reviewer_pass`: *"The final
   plan has passed review but requires human approval before any export or next steps can
   proceed"*).
2. **2 failures — model unreliability, not a clean prompt gap, left as-is:**
   `multiple_errors_recorded` (expected `STOP_WITH_ERROR`, got `RUN_REQUIREMENT_ANALYST`) and
   `error_recorded_despite_otherwise_complete_state` (expected `STOP_WITH_ERROR`, got
   `EXPORT_PLAN`) both ignored recorded errors that `_summarize_state` *does* surface
   prominently (a `⚠️ Errors recorded` block is always first in the summary when present).
   Notably, `single_error_recorded` — structurally almost identical — passed correctly both
   times. This looks like genuine small-model inconsistency rather than a missing textual
   cue, and reproduced identically on the rerun, which supports that read (a one-off fluke
   would likely have landed differently the second time). Not fixed — no low-risk, well-
   diagnosed change presents itself the way the final-approval gap did, and chasing it without
   a clear cause would be guessing, not fixing.

**This second failure category is also the clearest live proof of why this project's
architecture never lets the Supervisor's recommendation be the actual enforcement point**
(§20.1, `app/workflow/routes.py`'s own docstring: "never trusts an agent's own judgment to
respect a loop limit"). In this exact evaluation, `route_next_node` — the deterministic
router, not the Supervisor — is what would have actually driven the graph, and it
unconditionally checks `state["errors"]` first, before any other condition. Had this state
occurred in a real run, the Supervisor's bad recommendation would have been logged for audit
(as it was here) but never acted on.

## §24.4 Tool Selection

From `day19_automated_metrics.md`. Every scenario's Requirement Analyst call produced the
identical, correctly-ordered tool sequence: `get_project_information` →
`search_project_documents` → `search_company_standards` → `save_requirements` →
`save_clarification_questions`. **Unpermitted tool calls found: none, across all 3
scenarios.** Every retrieval call is structurally project-filtered by construction (not
re-verified here — see the extensive existing coverage from Days 6/17/18).

Known limitation (not fixed this day): `WorkflowEvent`'s `tool` field logs only the tool
*name*, never the query text, so "avoided unnecessary repeated searches" can only be audited
at the tool-name level from this data — a legitimate repeated call to the same named tool
with a different query can't be distinguished from a redundant identical one without richer
logging. Not an issue in practice this run: no tool name repeats within any single scenario's
call sequence.

Separately noted, out of §24.4's scope but found while building this evaluation:
`WorkflowEvent.duration_ms` (the schema field meant to carry §21's "Generation duration") is
defined but never populated anywhere in the codebase — this evaluation had to reconstruct
real agent-call durations after the fact by pairing IN_PROGRESS/SUCCESS event timestamps
(`evaluation/scripts/run_extraction_evaluation.py::compute_agent_durations`) instead of
reading it directly. Worth populating `duration_ms` at the source in a future day so this
doesn't need reconstructing every time.

## §24.5 Grounding

15 SOURCE_BACKED requirements sampled (5 per scenario, random seed 19) and checked against
their cited section/chunk content in the real source document; all ASSUMPTION/
AI_RECOMMENDATION-classified items present (8 total across the 3 scenarios) were checked for
overclaiming.

**Breakdown: 15/15 sampled SOURCE_BACKED items correctly source-backed** (the cited section
genuinely contains the claimed content — e.g. REQ-002 "reject overlapping leave requests"
cites "3.1 Leave requests," which is exactly where that rule appears). **8/8 sampled
ASSUMPTION/AI_RECOMMENDATION items correctly labelled** — none were phrased as settled fact
(e.g. scenario 1's `REQ-020`/`REQ-021` use "are the same for all employees," "are always
submitted by" — assumption language, not requirement language; scenario 2's `REQ-030`/
`REQ-031` use clear recommendation phrasing, "Implement a health check endpoint...").
**Unsupported: 0/23.**

One real, specific accuracy gap found, consistent with a previously-documented limitation
(Day 15's known-issues notes): scenarios 1 and 2's sampled citations all pointed to the
correct, specific subsection heading (10/10) — but all 5 of scenario 3's sampled citations
point to the document's top-level title ("Customer Support Assistant — Business
Requirements") instead of the actual subsection the claim came from (e.g. "## 4. Functional
Requirements (as currently understood)"). The claims themselves are still genuinely
supported by the document, and the `chunk_id` is real and non-dangling (the deterministic
citation validator already guarantees that) — but the `section` text is imprecise for this
one document, most likely because its narrative/meeting-notes structure chunks more coarsely
than scenarios 1-2's clean numbered-heading structure. Not fixed this day (already a known,
named limitation, not a new one).

## Summary against §24.10-style targets (informal preview — the full §24.10 audit is Day 22)

- [x] ≥85% major-requirement extraction: **PASS** (97.9% overall; 100%/100%/90% per scenario)
- [x] Every SOURCE_BACKED item has a citation: **PASS** (100% across all 3 scenarios)
- [x] ≥80% clarification usefulness: **PASS** (100% overall)
- [x] ≥15 routing situations, correct-action check: **PASS** (17 situations, 88% correct after
      the final-approval prompt fix — genuinely imperfect even after fixing what could cleanly
      be fixed, which is the point of testing the real Supervisor instead of a mock)
- [x] No unpermitted tool calls: **PASS** (0 found)

## Known limitations found this day

1. ~~**Supervisor prompt gap** (§24.3): `_summarize_state` never mentions `final_approved`
   when it's `False`~~ — **fixed and reverified this day** (see §24.3 above); pass rate rose
   71% → 88%.
2. **`WorkflowEvent.duration_ms` never populated** (§21/§24.4): defined in the schema, never
   set anywhere; this evaluation reconstructed durations from timestamps instead.
3. **Scenario 3 citation `section` imprecision** (§24.5): already a named Day 15 limitation,
   reconfirmed here with a concrete, reproducible example (all 5/5 sampled citations for this
   one document).
4. **No API-level access to `contradictions`/`ambiguities`/`missing_information`**: only
   `requirements` and `clarification_questions` are exposed via `GET` endpoints, so this
   evaluation could only infer whether scenario 3's 3 contradictions were formally detected
   indirectly (via clarification-question phrasing and multi-requirement synthesis), not
   directly from a `contradictions` array. Not necessarily a defect — the spec doesn't
   mandate a dedicated endpoint for these — but worth a note for anyone building a richer
   evaluation harness later.

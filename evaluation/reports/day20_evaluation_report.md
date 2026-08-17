# Day 20 Evaluation Report — Plan Quality, Reviewer Effectiveness, Repeatability

Spec sections covered: §24.6, §24.7, §24.8.
Raw data: `evaluation/reports/day20_repeatability_evaluation.md`,
`evaluation/reports/day20_repeatability_run{1,2,3}_plan.json`,
`evaluation/reports/day20_seeded_error_evaluation.md`. All numbers below come from real,
live `qwen3:4b-instruct` runs against scenario 2 (E-Commerce Payment Integration) — no mocked
model output for any headline number.

## §24.8 Repeatability

Target: compare number of requirements, epics, stories, requirement coverage, unsupported
claims, schema-validation failures, and reviewer decisions across 3 independent runs of the
same project.

| Run | Status | Reqs | Epics | Stories | Reviewer decision | Revision cycle fired? | Schema-valid? | Validation errors | Traceability coverage | Total live-agent time |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | COMPLETED | 30 | 17 | 17 | REVISION_REQUIRED (final) | Yes | **No** | 1 | 71.0% | 108.5 min |
| 2 | COMPLETED | 30 | 17 | 16 | PASS_WITH_WARNINGS | No | Yes | 0 | 86.5% | 59.3 min |
| 3 | COMPLETED | 32 | 14 | 14 | REVISION_REQUIRED (final) | Yes | **No** | 1 | 92.6% | 97.4 min |

**Requirement/epic/story counts are stable** (30-32 requirements, 14-17 epics, 14-17 stories
— low variance for an inherently non-deterministic small-model process, all three runs
converged on a recognizably similar plan shape for the same input document).

**Reviewer decisions and schema validity are *not* stable** — this is the most important
repeatability finding. Run 2 passed cleanly (schema-valid, no revision needed,
PASS_WITH_WARNINGS) in 59.3 minutes. Runs 1 and 3 both triggered a revision cycle (Reviewer
said REVISION_REQUIRED, Planning revised once per §20.1's single-revision limit, Reviewer
re-ran) and **both still ended with `REVISION_REQUIRED` as the final decision and
`validation_is_valid=False`** — meaning the single allowed revision did not actually fix the
underlying structural problem in either case, and the workflow correctly fell through to
`WAIT_FOR_FINAL_APPROVAL` anyway per §7.4 ("stop for human review even when warnings remain")
rather than looping again. This is the guardrail working exactly as designed — but it also
means 2 of 3 independent runs of the identical input produced a plan that never became
schema-valid within the allowed revision budget. Total live-agent time varied nearly 2x across
runs (59.3 to 108.5 minutes) — largely driven by whether a revision cycle fired (each
Planning/Reviewer pass costs another ~2000s/~700s respectively) rather than by
Requirement-Analyst-stage variance alone.

**Unsupported claims**: not directly comparable as a single number across runs from this data
(`validate_project_plan`'s `errors` count structural issues — duplicate IDs, dangling
citations, missing mandatory fields — not semantic "unsupported claim" judgments, which are
the Reviewer's own LLM-judged territory, see §24.7 below for that class of finding
specifically).

## §24.6 Project-Plan Quality

Manually scored 1-5 against Run 1's plan (`day20_repeatability_run1_plan.json`), with concrete
evidence cited for each score — not a bare number.

| Dimension | Score | Evidence |
|---|---|---|
| Requirement coverage | 3/5 | 71.0% of requirements (22/31) trace to at least one epic; 9 requirements have no downstream epic/story link at all. The matrix honestly reports its own gap rather than overclaiming full coverage — a real strength — but the underlying coverage itself is incomplete. |
| Epic quality | 5/5 | All 17 epics are specific, non-generic, and directly traceable to source language (e.g. "Enforce PCI-DSS Compliance by Preventing Raw Card Data Storage"); 15 correctly classified SOURCE_BACKED with real citations, 2 correctly classified AI_RECOMMENDATION (health-check endpoint, webhook delivery logging) rather than being smuggled in as requirements. |
| User-story quality | 3/5 | Correct "As a [persona], I want [capability], so that [business benefit]" format throughout, personas vary sensibly (customer / system / support agent), each tied to a real epic with citations. But **`suggested_story_points` is `null` for all 17 stories** — a spec §13.6 field left entirely unpopulated, not just conservatively estimated. |
| Acceptance-criteria testability | 4/5 | Consistent, correct Given/When/Then format; criteria are concrete and verifiable (e.g. "the system does not store any raw card numbers or cardholder data in its database"). Weakness: several stories (US-002, US-003, US-006) have only 1 AC each, thin for real payment-flow stories that plausibly need a failure-path AC too. |
| Dependency quality | 3/5 | 10 dependencies with logically sound epic-to-epic relationships (e.g. payment-record-creation before refund capability, webhook-exposure before idempotency handling) and correctly chosen `dependency_type`. Weakness: `description` is empty on every sampled dependency — the "Description" and "Suggested resolution" fields spec §13.8 asks for are present in schema but not populated in practice. |
| Risk relevance | 5/5 | 7 risks, genuinely specific to this domain, not generic boilerplate (Stripe-outage risk, and — notably — 3 risks that independently re-derive the *same* ambiguities a good Requirement Analyst should flag: "definition of 'normal load' is not clearly defined," "definition of 'duplicate' webhook delivery is not specified," "definition of 'completed payment' is ambiguous" — real cross-agent consistency, each with a concrete mitigation). |
| Sprint-plan usefulness | 2/5 | 6 sprints with a sensible dependency-ordered narrative (foundational flow → webhooks/audit → failure recovery → refunds → observability → validation) and all 17 stories scheduled (`unscheduled_story_ids` empty). But every `story_point_total` is `0` (cascades from the missing story points above), `dependency_considerations` is empty despite 10 real dependencies existing, and Sprint 6 has a stated goal ("validate all requirements... traceability") but **zero stories assigned to it** — a sprint that exists only on paper. |
| Traceability | 3/5 | Matrix is present and structurally correct (31 rows, real requirement_id/epic_id/story_id/AC linkage where it exists) and — again — honestly reports its own 9-requirement gap rather than hiding it. Scored the same as "requirement coverage" above since they measure the same underlying artifact from two angles. |

**Overall**: a genuinely usable first draft — epics and risks are the strongest artifacts
(5/5 each, specific and well-grounded), acceptance criteria are solid (4/5). The weakest
dimension by a clear margin is sprint-plan usefulness (2/5), which traces back to a single
root cause propagating through three dimensions: **story points are never populated**,
which zeroes every sprint's point total and makes the sprint plan much less useful to a PM
than its otherwise-sensible sequencing suggests. This is the single highest-value finding
from this evaluation for a future fix.

## §24.7 Reviewer Effectiveness — 6 Seeded Errors

Full data: `evaluation/reports/day20_seeded_error_evaluation.md` /
`day20_seeded_error_evaluation.json`. Each seed was applied to a real, previously-valid plan
(a fresh 4th live pipeline run — see "known limitations" below for why Run 1's original plan
couldn't be reused) and run through the real Reviewer Agent (or caught earlier by schema
validation).

| Seed | Outcome | Decision | Duration | Attribution confidence |
|---|---|---|---|---|
| story_without_epic | Rejected by `ProjectPlan`'s Pydantic validator before reaching the Reviewer at all | — | 0.0s | **Certain** — the exact seeded `epic_id` appears in the `ValidationError` message |
| missing_acceptance_criteria | Rejected by `ProjectPlan`'s Pydantic validator before reaching the Reviewer at all | — | 0.0s | **Certain** — the exact seeded story's empty AC list appears in the `ValidationError` message |
| invalid_citation | Reviewer ran | REVISION_REQUIRED | 170.9s | **Likely, not directly confirmed** — see below |
| duplicate_story | Reviewer ran | REVISION_REQUIRED | 250.6s | **Certain, direct hit** — the report's `duplicate_stories` list names the exact seeded story `US-001-DUP` and describes it as "near-identical... with the same text and acceptance criteria as [US-001]" |
| unsupported_requirement | Reviewer ran | REVISION_REQUIRED | 295.9s | **Cannot confirm** — see below |
| circular_dependency | Reviewer ran | REVISION_REQUIRED | 203.9s | **Likely, not directly confirmed** — see below |

**The clean result**: `duplicate_story` is a direct, unambiguous hit — the Reviewer's own
semantic judgment (not a deterministic check; duplicate *content*, not duplicate *ID*, was
seeded specifically so schema validation couldn't block it) correctly named the exact
artifact and explained why. This is the single cleanest piece of evidence in this evaluation
that the Reviewer Agent does real semantic work, not just schema-checking.

**The "likely but not directly confirmed" results** (`invalid_citation`,
`circular_dependency`): both categories are backed by a deterministic check
(`validate_project_plan`'s dangling-citation check and DFS-based cycle detection
respectively) that **forces** `decision=REVISION_REQUIRED` via
`app/agents/reviewer.py::_force_revision_on_structural_failure` regardless of what the LLM
itself judges — so `REVISION_REQUIRED` firing for both is exactly the expected mechanism at
work. But this evaluation script only captured the `unsupported_claims` /
`duplicate_stories` / `dependency_issues` fields of `ReviewerReport`, not
`validate_project_plan`'s own direct structural-error list or `revision_instructions` — so
the specific dangling-citation / circular-dependency finding isn't visible in what got
captured; what's visible instead is a different, genuine, pre-existing issue already present
in this run's baseline plan (a "Mobile Device Support" epic whose evidentiary basis the
Reviewer independently flagged as weak). The *decision* is attributable to the seed with high
confidence given how the code is structured; the specific *issue text* is not verifiable from
this data.

**The one real miss/inconclusive result** (`unsupported_requirement`): this is the sole
category with **no deterministic backstop** — §7.4 check 7 ("are unsupported claims presented
as facts") is LLM-judgment-only by design (Day 13), so `REVISION_REQUIRED` firing here isn't
guaranteed by any mechanism other than the Reviewer actually noticing. The only
`unsupported_claim` visible in the captured output is the same pre-existing "mobile device
support" issue seen in `circular_dependency` above, not the seeded claim (a fabricated "50,000
transactions/sec across 12 regions" objective on EPIC-001). This evaluation **cannot conclude**
the Reviewer caught the seeded semantic-unsupported-claim defect specifically — it may have,
and simply reported the pre-existing issue first/instead in the fields captured, or it may
genuinely have missed it. This is the one place this evaluation's design has a real gap, noted
below rather than glossed over.

**Bonus finding, not part of the original 6 seeds**: the baseline plan used for this section
(a fresh 4th live run, not one of the 3 repeatability runs) independently surfaced its own
real defect — a "Mobile Device Support" epic (`EPIC-023`) with a dependency to
`EPIC-024` (PCI-DSS Compliance) that the Reviewer correctly flagged as lacking evidentiary
support, and an `ASSUMPTION`-classified story (`US-022`) about the same feature that the
Reviewer also correctly declined to treat as settled fact. Scenario 2's source document never
mentions mobile devices at all — this looks like the Planning Agent inventing scope beyond
what §7.3's planning rules allow ("avoid deciding technologies... not specified"), caught
correctly by the Reviewer independent of anything seeded here. Worth flagging as its own
finding, separate from the 6 planned seeds.

## Summary against §24.10-style targets (informal preview — the full §24.10 audit is Day 22)

- [x] Repeatability measured across 3 independent runs: **done** — counts stable, reviewer
      decisions/schema-validity genuinely variable (2/3 runs never reached schema-valid within
      the single-revision budget)
- [x] Plan quality scored 1-5 across all 8 named dimensions: **done** — overall usable draft,
      weakest area (sprint-plan usefulness, 2/5) traced to one root cause (missing story points)
- [x] Reviewer effectiveness on 6 seeded errors: **done** — 2/6 correctly rejected at the
      schema layer before review, 1/6 a clean direct semantic hit (duplicate_story), 2/6
      correctly triggered REVISION_REQUIRED via a deterministic backstop (attribution to the
      specific seed likely but not directly confirmed by this script's captured fields), 1/6
      inconclusive (unsupported_requirement — the one category with no deterministic
      backstop, and no evaluation-visible evidence either way)

## Known limitations found this day

1. **Missing story points across the board**: all 17 of Run 1's stories have
   `suggested_story_points: null` — worth checking whether this is systemic (every run, every
   scenario) or specific to this run; propagates into every sprint's `story_point_total` being
   `0`, meaningfully weakening sprint-plan usefulness.
2. **Empty dependency descriptions**: `Dependency.description`/`suggested_resolution` fields
   exist in the schema but were empty on every sampled dependency in Run 1's plan.
3. **Planning Agent scope invention, found via §24.7's baseline plan, not a seed**: the
   4th live run (seeded-error baseline) produced an epic/story pair about "mobile device
   support" with no basis anywhere in scenario 2's source document — the Reviewer correctly
   caught it, but it shouldn't have been generated in the first place per §7.3's "avoid
   deciding... scope not specified" planning rule. Worth a follow-up: is this a one-off, or
   does Planning invent scope more often than the Reviewer catches it?
4. **§24.7's evaluation script captured too narrow a slice of `ReviewerReport`** (only
   `unsupported_claims`/`duplicate_stories`/`dependency_issues`, not
   `validate_project_plan`'s own structural-error list or `revision_instructions`) — meaning
   3 of the 6 seeds' `REVISION_REQUIRED` decisions can't be cleanly attributed to the specific
   seeded defect from this data alone, only inferred from how the code is structured. A
   worthwhile Day 21/22 follow-up: capture the full report plus `validate_project_plan`'s
   direct output per seed for unambiguous attribution.
5. **A script bug in this day's own evaluation tooling** (not `app/` production code): the
   first live run of `run_seeded_error_evaluation.py`'s `write_report()` crashed on a
   str-slicing bug (assumed every issue was a string; `ReviewerIssue.model_dump()` dicts
   aren't) — after all 6 live Reviewer calls had already completed successfully. Fixed
   immediately; required one additional ~2h45m live pipeline run to recover a self-consistent
   baseline (the original run's plan couldn't be reused against a new project — its citations
   point to chunk_ids that only existed in the now-gone original project, which would have
   made every citation look dangling regardless of the seeded defect).

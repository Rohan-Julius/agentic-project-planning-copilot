# Day 25 Live Demo Rehearsal — Final Results

**Date:** 2026-08-23
**Run:** `proj_a148bad57505` (`tests/integration/test_evaluation_day22_live_verification.py`,
real Ollama `qwen3:4b-instruct` + real embedded Qdrant, `EMBEDDING_DEVICE=cpu`)

## Result: PASSED — `final_status: "COMPLETED"`, clean, no revision cycle needed

```json
{
  "project_id": "proj_a148bad57505",
  "final_status": "COMPLETED",
  "requirement_count": 24,
  "epic_count": 8,
  "story_count": 15,
  "traceability_coverage_pct": 100.0,
  "coverage_gap_count": 0,
  "validation_is_valid": true,
  "validation_error_count": 0,
  "citation_section_accuracy": "24/24",
  "stories_with_story_points": "15/15",
  "duration_ms_populated": true
}
```

| Stage | Outcome | Duration |
|---|---|---|
| Supervisor (route to RA) | SUCCESS | 12.3s |
| Requirement Analyst | SUCCESS | 422.7s (7.0 min) |
| Supervisor (route to Planning) | SUCCESS | 7.9s |
| Planning (full sequence: summary/scope → epics → stories → tasks/deps/RAID → sprint plan) | SUCCESS | 1213.7s (20.2 min) |
| Supervisor (route to Reviewer) | SUCCESS | 6.1s |
| Reviewer | SUCCESS | 69.8s |
| Supervisor (route to final gate) | SUCCESS | 9.9s |

**Total: 1751.79s (29 min 12s)** — the fastest full pipeline run observed this session (prior
runs ranged ~1–2.5h), on a genuinely simpler scenario (24 requirements vs. 29-35 in other
runs) plus the embedding-device fix removing GPU contention entirely.

Reviewer decision: **PASS_WITH_WARNINGS**, 0 revision instructions — no revision cycle
triggered. Plan approved via the scripted equivalent of the final human-approval gate
(`POST /plan/approve`, asserted 200).

## This was the 4th attempt — the first three each surfaced (and fixed) a real, distinct bug

This is worth reporting honestly rather than only showing the clean final result:

1. **Attempt 1** (`proj_ec4a5e5ad174`): completed Requirement Analyst (29 requirements) and
   epics (13 generated, 0 scope-invention drops) cleanly, then failed — Ollama itself returned
   an HTTP 500 (not a JSON-validation issue) during the stories call, and the existing
   retry-once policy (§20.1) only covered schema-validation failures, so a 5xx got zero
   retries. **Fixed**: `run_agent` now retries once on a transient `ollama.ResponseError` with
   `status_code >= 500` too (3 new regression tests).
2. **Attempt 2** (`proj_5124bd041230`): completed Requirement Analyst (31 requirements) and
   epics (31 generated, full 1-pass coverage, 0 drops) cleanly, then failed on the *same call*
   for a *compounding* reason — the stories call hit a `json_invalid` truncation on attempt 1
   (correctly retried per the fix above's sibling fix from earlier the same day), but the retry
   itself then hit a genuine Ollama 500, exhausting the single bounded retry. This is §20.1's
   "retry once, not open-ended" policy working exactly as designed, not a defect — but it
   motivated finding the *environmental* root cause rather than just accepting the coincidence:
   `EmbeddingService` had no explicit `device`, so `sentence-transformers` auto-selected `mps`
   (Apple Silicon GPU), contending with Ollama's own GPU-resident model on the same machine.
   **Fixed**: `Settings.embedding_device` (new, default `"cpu"`) is now threaded through
   explicitly, removing that contention (2 new regression tests).
3. **Attempt 3** (`proj_b26dab4945e8`): lost mid-run, not to a code bug — the session
   environment itself restarted (killing the background process and wiping the ephemeral
   scratchpad) partway through Requirement Analyst. No results recoverable; simply relaunched.
4. **Attempt 4** (`proj_a148bad57505`): **passed cleanly**, as reported above — no MPS
   auto-detection log line appeared at all this run (confirming the embedding-device fix took
   effect), and no transient-500 retry was needed either.

Three consecutive attempts each surfacing a genuinely different, real cause (a missing retry
path, an environmental GPU-contention risk, and an infrastructure restart) is a legitimate
reflection of how much can go wrong in a long-running, multi-stage local-LLM pipeline — each
one was root-caused and fixed (or, for the third, correctly identified as external and not
something to "fix" in application code) rather than dismissed or retried blindly.

## Scope-invention regression check (the original Day 25 ask)

Across all three completed-far-enough-to-check attempts (1, 2, and 4), zero epics or stories
were dropped by the new `_drop_ungrounded_items` backstop — meaning the model didn't attempt to
fabricate ungrounded scope in any of these particular runs. This doesn't prove the failure mode
can never recur (it's inherently a small-model probabilistic behavior), but it does confirm:
the fix doesn't wrongly reject legitimate epics/stories (coverage stayed 100% and every plan
validated cleanly), and the mechanism is unit-tested to reproduce and correctly catch the exact
Day 20 failure shape on demand, independent of whether this particular scenario happens to
trigger it live.

## Evidence for the §29 evaluation-results claims

This run independently confirms the numbers already reported in the README's Evaluation
results table hold on a fresh run, not just historically: 100% traceability coverage, 0
validation errors, 100% citation accuracy (24/24), 100% story-point coverage (15/15).

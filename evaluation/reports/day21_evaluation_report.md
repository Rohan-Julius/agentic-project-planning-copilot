# Day 21 Evaluation Report — Retrieval Evaluation

Spec section covered: §24.9. Reranking dropped from this day's scope (user decision — §32
stretch goal, already-measured severe generation latency across the pipeline made it not
worth pursuing; see `docs/PROJECT_PLAN.md` Day 21).

Raw data: `evaluation/reports/day21_retrieval_evaluation.md` / `.json`. Unlike Days 19-20,
this evaluation makes **zero live Ollama calls** — pure local embedding (`bge-small-en-v1.5`)
+ Qdrant vector search — so the entire 32-query run completes in ~8 seconds.

## Headline numbers

- **32 queries** across all 7 named categories (target: ≥30).
- **Correct source found: 28/28 applicable queries (100%)** — the 4 `no_answer` queries are
  excluded from this count by design (there is no "correct source" for a question with no
  answer; see below for how those were actually judged).
- **Citation valid: 32/32 (100%)** — every returned chunk carried a real `chunk_id` and
  `document_name`.
- **Mean latency: ~20ms per query.** Max observed: 48.5ms. This is retrieval-only latency
  (embedding the query + vector search) — nowhere near the multi-minute agent-generation
  latencies measured on Days 19-20, confirming retrieval itself is not the pipeline's
  bottleneck.
- **Zero cross-project retrieval leakage** — not a distinct query category run today (already
  extensively covered by Checkpoint 1 and Days 6/17/18's tests), but implicitly reconfirmed:
  every query's returned `document_names` matched only documents actually uploaded to that
  query's own target project.

## A real bug found and fixed before results could be trusted

The first live run showed all 3 `metadata_filtered` queries against company standards
returning **zero results** despite the target documents being indexed. Root cause:
`app/api/documents.py::upload_document` and `app/api/standards.py::upload_organizational_document`
both declared `document_type: str = ""` as a plain function parameter alongside an
`UploadFile` parameter — FastAPI requires such parameters to be declared `= Form(...)` to be
read from the same multipart body; without it, the value is silently never captured and stays
`""` regardless of what's actually sent. **This affected every file-uploaded document in the
entire application, project or organizational, not just this evaluation's synthetic data** —
any category/type-based filtering (§9.1's `document_types`, §9.2's `category`) has never
worked for a file-uploaded document since the endpoints were built. Documents created via the
text-input path (`DocumentTextCreate`, a JSON body) were unaffected — this bug only touched
the `UploadFile` + form-field code path.

Fixed: both parameters now declared `document_type: str = Form("")`. Verified with a targeted
diagnostic before and after (`document_type` went from always-`""` to correctly capturing
`"Definition of Ready"` etc.), plus two new regression tests
(`tests/unit/test_api_documents.py::test_upload_document_captures_document_type_from_form_data`,
`tests/unit/test_api_standards.py::test_upload_organizational_document_captures_document_type_from_form_data`).
After the fix, all 4 `metadata_filtered` queries pass.

## Findings by category

**Direct requirement retrieval (8/8 correct)**: clean, no issues — every query for a specific
stated requirement found the right document with the right content.

**Company-standard retrieval (6/6 correct)**: same — the 5 new `sample_documents/` standards
files (created this day; none existed before) are all correctly retrievable by topic.

**Multi-document retrieval (4/4 correct, with an honest caveat)**: this dataset has no case of
two genuinely *unrelated* documents whose content should jointly answer one query — every
scenario project has exactly one document. 3 of the 4 queries test the closest available
proxy (a query whose answer spans multiple *sections* of one document — a real hybrid-search
capability, just not literally "multiple documents"). The 4th targets the versioning
project specifically because it's the only place with >1 real `document_id`, but both share
one `document_name` (versioning working as intended — see below) — so it's an honestly
*version-spanning* multi-document case, not an unrelated-content one. Worth a note for anyone
extending this evaluation: a genuine multi-unrelated-document fixture doesn't exist yet.

**Metadata-filtered retrieval (4/4 correct after the fix above)**: confirms `document_types`/
`category` filtering works correctly *once the underlying data is actually captured* — the
filter logic itself (`app/services/retrieval_service.py`'s `MatchAny` on `document_type`) was
never the problem.

**Questions with no answer (4/4 judged honest, not a pass/fail metric)**: every `no_answer`
query still returns `top_k` results (there's no hard similarity threshold anywhere in the
retrieval layer — `search_project_documents`/`search_company_standards` always return their
requested `top_k`, however weak the match), but the *similarity scores* are a real, usable
signal: genuinely relevant queries scored 0.75-0.82, while all 4 no-answer queries scored
0.50-0.58 — a consistent, meaningful ~0.25 gap. This means the retrieval layer itself doesn't
refuse to answer (that's a deliberate design choice — a fixed cutoff would be brittle and
dataset-specific), but the score data an agent needs to recognize weak evidence and honestly
return `CLARIFICATION_REQUIRED`/`NO_SUPPORTING_SOURCE_FOUND` per §12.6 is genuinely there. Not
a defect; worth confirming with a future evaluation whether agents actually use this signal
(Day 19's evaluation already showed the Requirement Analyst correctly flagging genuinely
ambiguous scenario 3 content, which is a good sign this works in practice).

**Conflicting documents (3/3 correct, with an important mechanism caveat)**: all 3 queries
against scenario 3 (the deliberately-contradictory scenario) correctly surfaced both sides of
each conflict (e.g. "1 year" and "7 years" both present in the same query's results). But
`result_count` was **1** for every one of these queries despite `top_k=5` — meaning scenario
3's entire ~43-line document chunks into a very small number of chunks (likely close to one),
so both conflicting statements happen to land in the *same* chunk. The mechanism being tested
here is therefore "coarse chunking incidentally keeps both sides together," not "retrieval
intelligently ranks and returns multiple distinct conflicting chunks." This is a fragile form
of success — it wouldn't generalize to a larger document where the two sides of a conflict
might land in genuinely separate chunks, at which point retrieval's *ranking* (not just
chunking granularity) would need to surface both.

**Old and new document versions (3/3 correct, and the day's most important finding)**: fixed
a real flaw in this evaluation's own first attempt along the way — the initial fixture
uploaded the modified copy under a *different* filename
(`requirements_v2_scratch.md`), so `_next_version()` (which only increments when
`document_name` matches an existing record) treated it as an unrelated new document at
version "1.0", not "requirements.md" v2.0. Fixed by uploading the modified content under the
identical filename `"requirements.md"` (the filename sent to the server comes from the
upload's own field, independent of any local script path) — confirmed the second upload
correctly reports `document_version: "2.0"`.

With that fixed, the real finding: **every query against the versioning project returned
chunks from *both* version 1.0 and version 2.0 simultaneously** (`document_versions: ["1.0",
"2.0"]` on every one of the 3 queries), with no version-aware filtering, deduplication, or
"latest version only" preference anywhere in the retrieval path. A query for "annual leave
balance" genuinely returns both "20 days" (v1.0) and "25 days" (v2.0) side by side, with
nothing in the result telling the caller which one is current. This is a real, previously-
untested gap — document versioning (Days 3-4) tracks version *numbers* correctly, but nothing
in retrieval (Days 5-6) is version-*aware*. Added to the Known-Issues Backlog.

## Summary against §24.9's required measures

- [x] Recall@5: 28/28 applicable queries found their expected source (100%)
- [x] Correct source appears: yes, for all applicable queries (see above)
- [x] Citation correctness: 32/32 (100%) — every result carried real, valid citation fields
- [x] Retrieval latency: ~20ms mean, well within any reasonable bound
- [x] Incorrect cross-project retrieval: none observed (implicit — see Headline numbers)

## Known limitations found this day

1. **Fixed this day**: `document_type` form-field capture bug in both file-upload endpoints
   (see above) — a real, previously-undiagnosed defect affecting every uploaded document
   app-wide, not just this evaluation.
2. **Not fixed, added to the Known-Issues Backlog**: retrieval has no version awareness — a
   query against a document with multiple versions returns chunks from all versions
   indiscriminately, with no signal to the caller about which is current.
3. **Not a defect, but worth noting**: this evaluation's dataset has no genuine
   multiple-unrelated-documents-per-project fixture, so "multi-document retrieval" was tested
   as a proxy (multi-section-within-one-document) for 3 of its 4 queries.
4. **Not a defect**: no hard similarity-score cutoff exists anywhere in retrieval for
   "no answer" cases — a deliberate design choice, with real, usable score-gap evidence
   (~0.25) supporting that agents *could* reliably detect weak evidence from the score alone,
   though that judgment is correctly left to the calling agent, not hardcoded into the tool.

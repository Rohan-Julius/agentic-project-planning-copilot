# DOCX Export, Dependency Graph, and Agent Execution Replay — Implementation Report

**Date:** 2026-08-22
**Scope:** The three remaining §32 stretch-goal items that were still "Not attempted" after the
Tier 1 stretch-goals work: DOCX plan export, a visual dependency graph, and an agent-execution
replay mode. User-directed, post-Day-24 work — tracked in `docs/PROJECT_PLAN.md` under its own
dated section, not the 25-day numbering.

All three are pure rendering/formatting layers over data that already exists and is already
fully generated — **none of them touch an LLM or agent**, so unlike the Tier 1 regeneration
work, no live-Ollama verification was needed. Evidence here is test counts and one direct
structural check of the generated `.docx` file.

---

## 1. DOCX export

**What was built:** `GET /projects/{project_id}/export/docx`, plus inclusion in the existing
`GET .../export/zip` bundle. `build_docx_bytes` (`app/services/export_service.py`) mirrors
`build_markdown_export`'s exact traversal order (Summary → Scope → Epics → Stories → Technical
Tasks → RAID → Sprint Plan → Traceability) using `python-docx` (already a project dependency,
previously used only for parsing *input* documents) instead of markdown strings. Reuses the
existing `approval_label()`/`format_source_references()` helpers, so the DOCX export carries the
exact same `APPROVED`/`DRAFT_PENDING_APPROVAL` labeling as JSON/Markdown — never hardcoded.

**Deliberately out of scope:** No custom Word styling/branding (headers, fonts, a cover page) —
uses `python-docx`'s built-in heading levels and a `"List Bullet"`/`"Light Grid Accent 1"` table
style, matching the plain, unstyled presentation of the Markdown export rather than producing a
polished deliverable document.

**Evidence:** 4 new backend tests (`build_docx_bytes` structural + approval-label check,
`write_docx_file` never writes into the documents directory, `GET .../export/docx` returns a
valid, openable `.docx`) plus 2 updated existing tests (`404` checks and the zip-bundle test
now include `docx`). All pass.

---

## 2. Visual dependency graph

**What was built:** A List/Graph toggle in the Planning Workspace's Dependencies section.
`layoutDependencyGraph` (`frontend/src/utils/dependencyGraphLayout.ts`) is a pure TypeScript
function: Kahn's-algorithm topological layering assigns every dependency-referenced item a
`rank` (longest path from a root) and `order` (position within that rank); `DependencyGraph`
(`frontend/src/components/DependencyGraph.tsx`) renders that as a hand-rolled SVG — boxes for
nodes, arrows for edges, colored/dashed by `dependency_type` (BLOCKS/REQUIRES/RELATES_TO) using
this app's existing theme tokens (`--danger`, `--clarification`, `--border`), not new hardcoded
colors.

**Deliberately not a new npm dependency:** No `react-flow`/`d3`/`dagre`/etc. added — this
frontend's established style is plain CSS and hand-rolled components (see
`FileFormatCard.tsx`'s own comment on this), and the graphs involved (dependencies within one
sprint plan) are small enough that a full graph-library's pan/zoom/virtualization isn't needed.

**Deliberately excludes non-dependency items:** Only epics/stories/tasks that appear in at least
one `Dependency` edge are rendered — this visualizes the dependency structure, not the whole
backlog.

**Cycle handling:** A dependency cycle (which a real plan should never produce, but isn't
guaranteed against) doesn't hang the layout — any node still unranked after all in-degree-0
nodes are exhausted gets rank 0, and the whole layout is flagged `cyclic`, which the UI surfaces
as a visible warning rather than silently rendering a subtly wrong graph.

**Evidence:** 5 new frontend unit tests (`dependencyGraphLayout.test.ts`) covering a simple
chain, an empty graph, a diamond shape (shared descendant not duplicated), cycle detection, and
label resolution. All pass. Full frontend suite: `tsc -b` clean, `vite build` succeeds, `oxlint`
exit 0, `vitest run` 67/67 (up from 62).

---

## 3. Agent execution replay

**What was built:** A step/scrub mode added directly to the existing `AgentExecutionScreen` —
Play/Pause, step forward/back, and a range-slider scrubber over the `WorkflowEvent[]` array that
screen already fetches. No new backend endpoint: `GET /projects/{id}/workflow/events` already
returns exactly the data replay needs.

**Deliberate scope boundary:** Replay operates on the *latest* workflow run only, because that
endpoint is deliberately scoped that way already (its own docstring: "one run's live progress,
not a jumbled history of every past attempt"). Browsing *past* runs' events would need a new
backend endpoint (list past runs + fetch events by run id) and was left out — this is a real
scope boundary carried over from an existing, deliberate backend design decision, not something
overlooked.

**Evidence:** No new automated test — per this codebase's established convention, page/screen
components don't get dedicated component tests (only pure logic in `utils/*.ts` does; see
`versionDiff.ts`/`dependencyGraphLayout.ts` for that pattern). Verified via `tsc -b`, `vite
build`, and `oxlint`, all clean.

---

## Summary

| Item | Backend | Frontend | Tests | New dependency? |
|---|---|---|---|---|
| DOCX export | Done | Done (download card) | 4 new + 2 updated, all pass | None (python-docx already present) |
| Dependency graph | N/A | Done | 5 new, all pass | None (hand-rolled SVG) |
| Execution replay | N/A (reused existing endpoint) | Done | None (component, per convention) | None |

Full backend fast suite: run alongside this report — see `docs/PROJECT_PLAN.md`'s dated section
for the exact pass count. Full frontend suite: `tsc -b` clean, build succeeds, lint clean, 67/67
vitest tests pass (up from 62 before this work).

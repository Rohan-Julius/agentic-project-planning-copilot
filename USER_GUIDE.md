# User Guide

This guide is for the person actually using the tool day-to-day — a project manager, business
analyst, or scrum master — not a developer. It walks through every screen in the real order
you'll use them, plus a short FAQ. For setup instructions, see the main
[README](README.md#quick-start).

## First project, start to finish

1. Open the app and click **New project** on the Dashboard.
2. Fill in the project's name, description, business domain, methodology, expected duration,
   team composition, target platforms, and known technology constraints. Methodology is fixed
   to Agile/Scrum for this tool — every project gets a sprint plan, not a milestone plan.
3. On the **Document Workspace**, upload one or more requirement documents (PDF, DOCX, TXT, or
   Markdown) — or paste text directly via **Add text**. Give each document a category if you
   want it filterable later.
4. Click **Index documents**. This step is required and separate from uploading — until a
   document is indexed, the agents can't find anything in it. (If you skip this, "Run
   requirement analysis" will honestly report finding nothing rather than inventing content —
   that's the system working correctly, not a bug, but it's confusing the first time.)
5. Click **Run requirement analysis** to start the agentic workflow. You'll be taken straight
   to the Agent Execution screen — the request itself can take several minutes to tens of
   minutes on a local model, so the screen shows live progress rather than making you wait on
   a spinner.
6. When the workflow pauses for clarification, follow the link to the **Clarification
   Workspace**, answer what you can, then click **Approve clarifications** — planning will not
   start until you do this, even if there's nothing to answer.
7. Once planning and review finish, follow the link to the **Reviewer Screen**, read the
   findings, and click **Approve plan** — this is the only way a plan becomes "approved"; the
   agents can never do this themselves.
8. Go to the **Export Screen** and download JSON, Markdown, Jira CSV, or a ZIP bundle.

## Screen by screen

### Dashboard

Lists your projects and their status. If a workflow run hit an unrecoverable error, you'll see
"Workflow stopped with an error" here rather than a silent failure.

### Create Project

Captures name, description, business domain, methodology, expected duration, team composition,
target platforms, and known technology constraints. This context is fed to the agents later —
the more accurate it is, the better the generated plan reflects your real team and constraints.

### Document Workspace

Where you upload and manage the raw material the agents work from.

- **Upload files** — PDF, DOCX, TXT, or Markdown. Uploading a file with the same name as an
  existing document creates a new *version* of it (see [Documentation](README.md#documentation)
  → Developer Guide for how versioning works); a different filename is always treated as a
  brand-new document.
- **Add text** — paste requirement text directly instead of uploading a file, with the same
  document name/category/content fields.
- **Index documents** — required before the agents can search anything in what you just
  uploaded. Indexing is idempotent — running it again only processes documents that haven't
  been indexed yet, it won't re-embed everything from scratch.
- **Run requirement analysis** — starts the agentic workflow. This button is disabled until
  you've indexed at least once, and disabled again while a run is already in progress for this
  project (you can't accidentally start two overlapping runs).
- **View agent execution** — appears once a run is active, taking you to live progress.

### Company Standards

A separate, project-independent workspace for your organization's reusable templates —
Definition of Ready, Definition of Done, security checklists, testing standards, estimation
guidance, story-point scale, and similar. Upload/index these once; every project's Planning
and Requirement Analyst agents can then draw on them (e.g. to size story points against your
team's real Fibonacci scale instead of guessing).

### Agent Execution

Live progress for the current workflow run — which agent is active, what it's doing, whether
human input is required next. This screen intentionally shows **safe summaries only** — it
never exposes the model's raw internal reasoning, by design (spec §16.4). If the run is paused
waiting on you, a link to the right workspace (clarification or final approval) appears here.

### Clarification Workspace

Every clarification question the Requirement Analyst raised — things it genuinely couldn't
determine from the documents alone (a missing performance target, an unnamed payment provider,
a contradiction between two documents, etc.), each with the reason it was asked and the
supporting source text. For each question you can:

- **Answer** it directly.
- Mark it **deferred** or **not applicable**.
- Edit the question text itself if it needs clarifying.

Once you're done, click **Approve clarifications** — this is always available, even if there
are zero questions to answer, because approving this stage is what unblocks planning
regardless of how many (or how few) questions came up.

### Planning Workspace

The generated plan itself, organized into sections: **Summary**, **Scope** (in scope / out of
scope / assumptions / constraints), **Requirements**, **Epics**, **Stories** (with Given/When/
Then acceptance criteria, story points, and priority), **Tasks**, **Dependencies**, **RAID
Log** (Risks, Assumptions, Issues, Dependencies), **Sprint Plan**, and a **Traceability
Matrix** linking every requirement through to the acceptance criteria addressing it. Every
item is tagged with its grounding classification — see [Understanding classification
labels](#understanding-the-classification-labels) below.

### Reviewer Screen

The independent Reviewer Agent's findings: its decision (PASS / PASS_WITH_WARNINGS /
REVISION_REQUIRED), any missing requirements, unsupported claims, duplicate stories, weak or
missing acceptance criteria, traceability gaps, and dependency issues it found. If it asked for
a revision, the Planning Agent gets exactly one automatic attempt to address it — after that,
the plan comes back here regardless of whether every issue was resolved, because the workflow
is designed to always stop for a human at this point rather than loop indefinitely. Click
**Approve plan** when you're satisfied — this is the only action that marks a plan approved.

### Export Screen

Download the approved plan as JSON, Markdown, a Jira-compatible CSV, or a ZIP bundling all of
the above plus the Reviewer's report. Exports always reflect the *current* plan version, so if
you re-approve after an edit, downloading again gets the latest content — you're never stuck
with a stale export from earlier in the process.

## Understanding the classification labels

Every important generated item (a requirement, epic, story, risk, assumption) is labelled with
exactly one of:

- **SOURCE_BACKED** — directly supported by your uploaded documents, with a real citation
  (document, page, section) you can check yourself.
- **CLARIFICATION_BACKED** — based on an answer you gave in the Clarification Workspace, not
  the original documents.
- **ASSUMPTION** — an explicit assumption the agent is stating, not hiding.
- **AI_RECOMMENDATION** — a suggestion outside what was actually requested — useful, but not
  something you asked for, so treat it as optional.

This exists so you can always tell what's a fact from your own documents versus what the AI is
suggesting — the system is designed to never blur that line silently.

## FAQ

**Why can't I skip straight to planning?** The two approval gates (clarifications, final plan)
are mandatory by design — the tool is meant to produce a *reviewable draft*, never a final
decision made without you. Planning simply won't start until you approve the clarification
stage, even with zero questions.

**Why does everything take so long?** This runs entirely on a local model on your own
hardware, with no cloud API. A single agent call can take anywhere from a couple of minutes to
over an hour depending on your machine and document size — see
[Known limitations](README.md#known-limitations) for real numbers.

**What happens if I approve clarifications with unanswered questions?** They're recorded as
deferred/not-applicable and the workflow proceeds — this is an explicit, allowed choice, not an
error state.

**Story points look like plain integers — are they guaranteed?** No — they, and every priority
suggestion, are always labelled as suggestions, never as commitments. Treat them as a
starting point for your own estimation conversation.

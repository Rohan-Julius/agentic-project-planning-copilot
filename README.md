# Agentic Project Planning Copilot

A local, open-source agentic AI proof of concept that converts raw software requirement
documents into a reviewable, exportable project-planning package — epics, user stories,
acceptance criteria, technical tasks, dependencies, risks, and a sprint/milestone plan —
with human approval gates and Jira-compatible export. Runs entirely locally; **no paid
LLM API required**.

Authoritative specification: [problem_statement.md](problem_statement.md).

## Why agentic (not one big prompt)

Four specialist agents — **Supervisor, Requirement Analyst, Planning, Reviewer** — each
with a clear responsibility, coordinated by a **LangGraph** state graph with shared state,
conditional routing, two human approval gates, and a single bounded revision cycle.
Mechanical work (parsing, chunking, embedding, validation, traceability, export) is
deterministic Python; only reasoning is agentic. See [docs/DAY1_UNDERSTANDING.md](docs/DAY1_UNDERSTANDING.md)
and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Stack

Python 3.12 · FastAPI · LangGraph · Ollama (`qwen3:4b-instruct`) ·
Sentence-Transformers (`BAAI/bge-small-en-v1.5`) · Qdrant · SQLite · React · Docker Compose.

## Status

Under active development on a 25-day plan — see the task board:
[docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md). This README is finalized on Day 24.

## Local development (early)

Prerequisites: Python 3.12 and [Ollama](https://ollama.com) running `qwen3:4b-instruct`.
No Qdrant install or Docker is required for local dev — the app defaults to an embedded,
file-backed Qdrant store under `DATA_DIR/qdrant_local`. Config is env-var driven — copy
`.env.example` to `.env`. To use a Qdrant server instead (e.g. the Docker demo topology),
set `QDRANT_URL` in `.env`.

```bash
cp .env.example .env
pip install -e ".[dev]"
uvicorn app.main:app --reload      # http://localhost:8000/health
pytest                             # run tests
```

## Repository layout

```
app/          FastAPI backend: agents, workflow, tools, api, database, models, schemas, services, prompts
frontend/     React UI (initialized Day 3, completed Day 14)
tests/        unit + integration tests
evaluation/   synthetic scenarios, expected results, scripts, reports (spec §23, §24)
sample_documents/  synthetic requirement docs
docs/         architecture, project plan, guides
```

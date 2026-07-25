"""FastAPI application entry point.

Day 1 provides the app skeleton and the /health endpoint (spec §18). Feature routers
(projects, documents, workflow, plan, export) are added on their respective days.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import clarifications, documents, plan, projects, requirements, standards, workflow
from app.config import get_settings
from app.database.session import init_db

app = FastAPI(
    title="Agentic Project Planning Copilot",
    description="Local agentic AI that turns raw requirements into a reviewable project plan.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(documents.router)
app.include_router(requirements.router)
app.include_router(clarifications.router)
app.include_router(standards.router)
app.include_router(workflow.router)
app.include_router(plan.router)


@app.on_event("startup")
def _on_startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe (spec §18)."""
    settings = get_settings()
    return {
        "status": "ok",
        "llm_model": settings.llm_model,
        "embedding_model": settings.embedding_model,
    }

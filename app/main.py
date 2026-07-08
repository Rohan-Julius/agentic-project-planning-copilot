"""FastAPI application entry point.

Day 1 provides the app skeleton and the /health endpoint (spec §18). Feature routers
(projects, documents, workflow, plan, export) are added on their respective days.
"""
from __future__ import annotations

from fastapi import FastAPI

from app.config import get_settings

app = FastAPI(
    title="Agentic Project Planning Copilot",
    description="Local agentic AI that turns raw requirements into a reviewable project plan.",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe (spec §18)."""
    settings = get_settings()
    return {
        "status": "ok",
        "llm_model": settings.llm_model,
        "embedding_model": settings.embedding_model,
    }

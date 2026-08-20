"""FastAPI application entry point.

Day 1 provides the app skeleton and the /health endpoint (spec §18). Feature routers
(projects, documents, workflow, plan, export) are added on their respective days.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    analysis_findings,
    clarifications,
    dashboard,
    documents,
    export,
    plan,
    projects,
    requirements,
    review,
    standards,
    workflow,
)
from app.config import get_settings
from app.database.session import init_db
from app.services.vector_service import VectorServiceUnavailableError

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Planning Copilot",
    description="Local agentic AI that turns raw requirements into a reviewable project plan.",
    version="0.1.0",
)

@app.exception_handler(VectorServiceUnavailableError)
async def vector_service_unavailable_handler(
    request: Request, exc: VectorServiceUnavailableError
) -> JSONResponse:
    """§25 'Chroma/Qdrant unavailable': a clean 503 instead of an unhandled 500 — the
    frontend's ApiError (frontend/src/api/client.ts) reads `detail` the same way it does for
    every other error response in this app. Registered via `@app.exception_handler` (not the
    `@app.middleware` catch-all below): FastAPI wires a handler for a specific exception type
    into Starlette's `ExceptionMiddleware`, which always sits *inside* CORSMiddleware, so its
    response automatically comes back with CORS headers with no extra effort.
    """
    logger.warning("Vector store unavailable: %s", exc)
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.middleware("http")
async def catch_unhandled_exceptions(request: Request, call_next):
    """Last-resort safety net (§25 general failure-path hardening) — never replaces a
    specific `@app.exception_handler` (register one instead when a new failure mode is
    understood), but guarantees any future unhandled exception still comes back as a clean,
    CORS-safe JSON error instead of Starlette's plain-text 500.

    Deliberately **not** a `@app.exception_handler(Exception)` — Starlette wires a handler
    registered for the bare `Exception` class into `ServerErrorMiddleware`, which is always
    the *outermost* layer (wraps CORSMiddleware itself), so a response built there never
    passes back through CORSMiddleware and never gets CORS headers — the browser reports
    that as a bare "Failed to fetch" with no usable detail (diagnosed docs/PROJECT_PLAN.md
    Day 14). Catching here instead, inside a normal middleware registered *before*
    CORSMiddleware (Starlette makes the most-recently-added user middleware outermost, so
    registering this one first keeps CORSMiddleware outside it), means the JSONResponse this
    returns flows back out through CORSMiddleware exactly like any ordinary response.
    """
    try:
        return await call_next(request)
    except Exception:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error."})


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router)
app.include_router(projects.router)
app.include_router(documents.router)
app.include_router(requirements.router)
app.include_router(analysis_findings.router)
app.include_router(clarifications.router)
app.include_router(standards.router)
app.include_router(workflow.router)
app.include_router(plan.router)
app.include_router(review.router)
app.include_router(export.router)


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

"""LangGraph checkpointer provider (Day 7, DESIGN.md §7.5).

A persistent, SQLite-backed checkpointer is required so the `clarification_gate`/
`final_gate` interrupts survive across separate HTTP requests — the process handling
`clarifications/approve` (Day 10) or `plan/approve` (Day 14) is not necessarily the same
one that handled `workflow/start`. Verified against a fresh `sqlite3.connect` + fresh
compiled graph (not just re-invoking the same in-memory object) — see
docs/DAY7_UNDERSTANDING.md.
"""
from __future__ import annotations

import sqlite3
from functools import lru_cache

from langgraph.checkpoint.sqlite import SqliteSaver

from app.config import get_settings


@lru_cache
def get_checkpointer() -> SqliteSaver:
    """Process-wide singleton (FastAPI-dependency-overridable in tests, same pattern as
    `get_vector_service`/`get_embedding_service`).
    """
    settings = get_settings()
    path = settings.checkpoint_db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    return saver

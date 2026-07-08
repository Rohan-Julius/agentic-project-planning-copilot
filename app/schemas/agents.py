"""Supervisor Agent decision schema (spec §7.1, §14 — reproduced verbatim)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.enums import SupervisorAction


class SupervisorDecision(BaseModel):
    next_action: SupervisorAction
    reason: str
    required_inputs: list[str] = Field(default_factory=list)

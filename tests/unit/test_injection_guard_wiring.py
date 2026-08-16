"""Prompt-injection guard-wiring tests (spec §20.3) — every Planning/Reviewer system prompt
must include the module's injection-defense text. Introspects each module's globals rather
than hardcoding a list of prompt names, so a future new system prompt is covered
automatically instead of silently shipping without the guard.
"""
from __future__ import annotations

import app.agents.planning as planning_module
import app.agents.reviewer as reviewer_module


def _system_prompt_constants(module) -> dict[str, str]:
    return {
        name: value
        for name, value in vars(module).items()
        if name.endswith("_SYSTEM_PROMPT") and isinstance(value, str)
    }


def test_every_planning_system_prompt_includes_the_injection_guard():
    prompts = _system_prompt_constants(planning_module)
    assert len(prompts) >= 5, "expected at least 5 Planning system prompts (Day 11-13 calls)"
    for name, prompt in prompts.items():
        assert planning_module._INJECTION_GUARD in prompt, f"{name} is missing the injection guard"


def test_every_reviewer_system_prompt_includes_the_injection_guard():
    prompts = _system_prompt_constants(reviewer_module)
    assert len(prompts) >= 1, "expected at least 1 Reviewer system prompt"
    for name, prompt in prompts.items():
        assert reviewer_module._INJECTION_GUARD in prompt, f"{name} is missing the injection guard"

"""Shared agent runner with Ollama structured output (DESIGN.md §8, spec §14)."""
from __future__ import annotations

import json
import logging
from typing import Any, Callable

import httpx
import ollama
from pydantic import BaseModel, ValidationError

from app.config import get_settings

logger = logging.getLogger(__name__)


class AgentError(Exception):
    """Agent execution failed after max retries."""

    def __init__(self, agent_name: str, error: str):
        self.agent_name = agent_name
        self.error = error
        super().__init__(f"{agent_name}: {error}")


def run_agent(
    agent_name: str,
    prompt: str,
    output_model: type[BaseModel],
    tools: list[Callable] | None = None,
    *,
    max_retries: int = 1,
) -> BaseModel:
    """Execute an agent via Ollama with structured JSON output.

    Flow:
    1. Call Ollama with prompt + JSON schema from output_model
    2. Parse and validate response
    3. On validation error: feed error back to agent, retry (max 1)
    4. On second failure: raise AgentError

    Args:
        agent_name: for logging/errors (e.g., "supervisor", "requirement_analyst")
        prompt: full prompt (injected into system + user messages already)
        output_model: Pydantic model defining expected JSON shape
        tools: list of tools agent can call (unused for Supervisor, used by others)
        max_retries: max attempts after first failure (default 1)

    Returns:
        Instance of output_model

    Raises:
        AgentError: if schema validation fails twice
    """
    settings = get_settings()
    schema = output_model.model_json_schema()

    full_prompt = (
        "You are a helpful assistant. Return valid JSON only, no other text.\n"
        f"{prompt}"
    )

    attempt = 0
    last_error = None

    while attempt <= max_retries:
        attempt += 1
        try:
            logger.debug(f"[{agent_name}] attempt {attempt}/{max_retries + 1}")

            # Call Ollama with structured output (format parameter enforces JSON schema).
            # Tuned specifically for qwen3:4b-instruct (spec §15's recommended default,
            # what this app is actually run against):
            #   - think=False: qwen3 defaults to emitting a large hidden chain-of-thought
            #     block before its answer. 
            #   - keep_alive="30m": agents that make several sequential calls (Planning
            #     does 4) can leave Ollama idle between them long enough for the default
            #     keep-alive to unload the model.
            #   - num_ctx=32768: the default context window silently truncates long
            #     prompts — losing part of the prompt an agent needs.
            #   - num_predict=8192: bounds worst-case output length so a degenerate
            #     repetition loop can't run for many extra minutes once it starts.
            #     (4096 was tried first and was too low — a real, non-degenerate
            #     RequirementAnalysisResult for a modest document legitimately needs
            #     more than that and got cut off mid-string, producing invalid JSON.)
            response = ollama.generate(
                model=settings.llm_model,
                prompt=full_prompt,
                format=schema,
                stream=False,
                think=False,
                keep_alive="30m",
                options={
                    "temperature": 0.3,  # Low temp for deterministic routing
                    "num_ctx": 32768,
                    "num_predict": 8192,
                },
            )

            # response["response"] is the model's output (guaranteed valid JSON by Ollama)
            json_str = response["response"].strip()

            # Parse and validate
            result = output_model.model_validate_json(json_str)
            logger.debug(f"[{agent_name}] success on attempt {attempt}")
            return result

        except (json.JSONDecodeError, ValidationError) as e:
            last_error = str(e)
            logger.warning(
                f"[{agent_name}] validation error on attempt {attempt}: {last_error}"
            )

            if attempt < max_retries + 1:
                # Feed error back to agent for retry
                full_prompt += (
                    f"\n\nError: your response was invalid JSON or did not match the expected schema.\n"
                    f"Details: {last_error}\n"
                    f"Please try again, returning only valid JSON matching the schema."
                )
            else:
                # Max retries exceeded
                raise AgentError(
                    agent_name,
                    f"Schema validation failed {max_retries + 1} times. Last error: {last_error}",
                )

        except httpx.ConnectError as e:
            raise AgentError(agent_name, f"Ollama not reachable at {settings.ollama_host}: {e}")
        except Exception as e:
            raise AgentError(agent_name, f"Unexpected error: {e}")

    # Unreachable (while loop guards it), but mypy needs this
    raise AgentError(agent_name, f"Max retries exceeded: {last_error}")

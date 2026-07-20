"""Tests for shared agent runner with Ollama structured output (spec §14, DESIGN.md §8)."""
import json
import pytest
from unittest.mock import Mock, patch
from pydantic import BaseModel, Field, ValidationError
from app.agents.runner import run_agent, AgentError


class SimpleDecision(BaseModel):
    action: str = Field(description="action to take")
    reason: str = Field(description="why this action")


def test_run_agent_valid_output():
    """Agent returns valid JSON matching schema — success path."""
    mock_response = {"response": '{"action": "proceed", "reason": "ready"}'}

    with patch("ollama.generate", return_value=mock_response):
        result = run_agent(
            agent_name="test",
            prompt="Decide",
            output_model=SimpleDecision,
            tools=[],
        )

    assert isinstance(result, SimpleDecision)
    assert result.action == "proceed"
    assert result.reason == "ready"


def test_run_agent_invalid_json_retries_once():
    """On validation error, agent retries once (error is fed back)."""
    # First call: invalid JSON (missing field)
    # Second call: valid JSON
    valid_json = '{"action": "retry_success", "reason": "learned"}'
    mock_calls = [
        {"response": '{"action": "incomplete"}'},  # Missing "reason"
        {"response": valid_json},
    ]

    with patch("ollama.generate", side_effect=mock_calls):
        result = run_agent(
            agent_name="test",
            prompt="Decide",
            output_model=SimpleDecision,
            tools=[],
            max_retries=1,
        )

    assert result.action == "retry_success"
    assert result.reason == "learned"


def test_run_agent_invalid_json_twice_raises():
    """On second validation failure, raises AgentError."""
    invalid_json = '{"action": "bad"}'  # Missing "reason" field

    with patch("ollama.generate", return_value={"response": invalid_json}):
        with pytest.raises(AgentError) as exc_info:
            run_agent(
                agent_name="test",
                prompt="Decide",
                output_model=SimpleDecision,
                tools=[],
                max_retries=1,
            )

    assert exc_info.value.agent_name == "test"
    assert "Schema validation failed 2 times" in str(exc_info.value)


def test_run_agent_ollama_unreachable():
    """If Ollama is down, raises AgentError with clear message."""
    import httpx

    with patch("ollama.generate", side_effect=httpx.ConnectError("Connection refused")):
        with pytest.raises(AgentError) as exc_info:
            run_agent(
                agent_name="test",
                prompt="Decide",
                output_model=SimpleDecision,
                tools=[],
            )

    assert "Ollama not reachable" in str(exc_info.value)

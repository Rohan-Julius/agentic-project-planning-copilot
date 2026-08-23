"""Tests for shared agent runner with Ollama structured output (spec §14, DESIGN.md §8)."""
import pytest
from unittest.mock import patch
from pydantic import BaseModel, Field
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


def test_run_agent_truncated_json_retry_asks_for_shorter_text():
    """Live-observed failure class (Tier 1 stretch-goals live verification, 2026-08-22): a
    response cut off by the num_predict output cap fails with pydantic's "json_invalid" error
    type, not a schema-shape mismatch. The retry prompt for that case must ask the model to
    shorten free-text fields, not just "match the schema" — the generic message doesn't address
    why the first attempt failed.
    """
    # Deliberately malformed to mimic truncation: an unterminated string, so
    # model_validate_json raises a ValidationError whose message contains "json_invalid".
    truncated_json = '{"action": "proceed", "reason": "this got cut off mid'
    valid_json = '{"action": "proceed", "reason": "short"}'
    mock_calls = [
        {"response": truncated_json},
        {"response": valid_json},
    ]

    with patch("ollama.generate", side_effect=mock_calls) as mock_generate:
        result = run_agent(
            agent_name="test",
            prompt="Decide",
            output_model=SimpleDecision,
            tools=[],
            max_retries=1,
        )

    assert result.action == "proceed"
    second_call_prompt = mock_generate.call_args_list[1].kwargs["prompt"]
    assert "cut off" in second_call_prompt
    assert "short" in second_call_prompt.lower()
    assert "match the expected schema" not in second_call_prompt


def test_run_agent_retries_once_on_transient_ollama_server_error():
    """Live-observed failure class (Day 25 demo rehearsal, 2026-08-22): Ollama itself returned
    an HTTP 500 mid-run (GPU-memory contention with the embedding model's concurrent MPS/Metal
    usage), not a malformed response — but the original retry-once policy (§20.1) only covered
    schema-validation failures, so this failed the whole run with zero retries. A 5xx is
    retried once, identically (no prompt mutation — the prompt wasn't the problem).
    """
    import ollama

    valid_json = '{"action": "proceed", "reason": "recovered"}'
    mock_calls = [
        ollama.ResponseError("Internal Server Error", status_code=500),
        {"response": valid_json},
    ]

    with patch("ollama.generate", side_effect=mock_calls) as mock_generate:
        result = run_agent(
            agent_name="test",
            prompt="Decide",
            output_model=SimpleDecision,
            tools=[],
            max_retries=1,
        )

    assert result.action == "proceed"
    # No prompt mutation on this retry class — both calls get the identical prompt.
    first_call_prompt = mock_generate.call_args_list[0].kwargs["prompt"]
    second_call_prompt = mock_generate.call_args_list[1].kwargs["prompt"]
    assert first_call_prompt == second_call_prompt


def test_run_agent_transient_ollama_server_error_twice_raises():
    """Two 5xx errors in a row (retries exhausted) still raises AgentError, not an infinite
    loop or a silent None."""
    import ollama

    with patch(
        "ollama.generate", side_effect=ollama.ResponseError("Internal Server Error", status_code=500)
    ):
        with pytest.raises(AgentError) as exc_info:
            run_agent(
                agent_name="test",
                prompt="Decide",
                output_model=SimpleDecision,
                tools=[],
                max_retries=1,
            )

    assert "Ollama returned an error" in str(exc_info.value)


def test_run_agent_client_error_from_ollama_is_not_retried():
    """A non-5xx ResponseError (e.g. a genuine bad request) fails immediately — retrying an
    inherently malformed request would just fail identically again, so this should NOT consume
    a retry attempt or call ollama.generate a second time.
    """
    import ollama

    with patch(
        "ollama.generate", side_effect=ollama.ResponseError("Bad Request", status_code=400)
    ) as mock_generate:
        with pytest.raises(AgentError):
            run_agent(
                agent_name="test",
                prompt="Decide",
                output_model=SimpleDecision,
                tools=[],
                max_retries=1,
            )

    assert mock_generate.call_count == 1


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

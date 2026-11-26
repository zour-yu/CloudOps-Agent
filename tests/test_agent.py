"""Unit tests for the Gemini tool-calling agent."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.agent import build_triage_prompt, run_triage_agent
from app.config import Settings


def test_build_triage_prompt_includes_url_and_logs() -> None:
    prompt = build_triage_prompt(
        question="Diagnose outage",
        target_url="http://127.0.0.1:8000/health",
        logs="ERROR timeout",
    )
    assert "Diagnose outage" in prompt
    assert "http://127.0.0.1:8000/health" in prompt
    assert "ERROR timeout" in prompt


def test_run_triage_agent_requires_api_key() -> None:
    with patch("app.agent.get_settings", return_value=Settings(gemini_api_key="")):
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            run_triage_agent("Check logs")


def test_run_triage_agent_tool_calling_loop() -> None:
    first_step = SimpleNamespace(
        type="function_call",
        id="call-1",
        name="parse_log_errors",
        arguments={"log_text": "2026-11-26T10:00:00Z ERROR Disk full"},
    )
    turn_1 = SimpleNamespace(id="int-1", steps=[first_step], output_text=None)
    turn_2 = SimpleNamespace(
        id="int-2",
        steps=[],
        output_text="Root cause: disk full. Free space on /var/log.",
    )

    mock_client = MagicMock()
    mock_client.interactions.create.side_effect = [turn_1, turn_2]

    result = run_triage_agent("Analyze these logs", client=mock_client, model="gemini-4-hydrogen")

    assert result["interaction_id"] == "int-2"
    assert "disk full" in result["summary"].lower()
    assert len(result["tool_calls"]) == 1
    assert result["tool_calls"][0]["tool"] == "parse_log_errors"
    assert result["tool_calls"][0]["output"]["error_line_count"] == 1
    assert mock_client.interactions.create.call_count == 2
    second_call_kwargs = mock_client.interactions.create.call_args_list[1].kwargs
    assert second_call_kwargs["previous_interaction_id"] == "int-1"


def test_run_triage_agent_falls_back_on_503() -> None:
    class ServiceUnavailableError(Exception):
        status_code = 503

    turn_1 = SimpleNamespace(id="int-fallback", steps=[], output_text="Healthy.")
    mock_client = MagicMock()
    mock_client.interactions.create.side_effect = [
        ServiceUnavailableError("503 service_unavailable"),
        turn_1,
    ]

    result = run_triage_agent(
        "Check service",
        client=mock_client,
        model="gemini-4-hydrogen",
        fallback_models=["gemini-3.5-flash-lite"],
    )

    assert result["summary"] == "Healthy."
    assert mock_client.interactions.create.call_count == 2
    assert mock_client.interactions.create.call_args_list[0].kwargs["model"] == "gemini-4-hydrogen"
    assert (
        mock_client.interactions.create.call_args_list[1].kwargs["model"]
        == "gemini-3.5-flash-lite"
    )


def test_run_triage_agent_raises_clear_error_when_all_models_503() -> None:
    class ServiceUnavailableError(Exception):
        status_code = 503

    mock_client = MagicMock()
    mock_client.interactions.create.side_effect = ServiceUnavailableError("503 service_unavailable")

    with pytest.raises(RuntimeError, match="All Gemini models failed"):
        run_triage_agent(
            "Check service",
            client=mock_client,
            model="gemini-4-hydrogen",
            fallback_models=["gemini-3.5-flash-lite"],
        )


def test_run_triage_agent_does_not_fallback_on_auth_error() -> None:
    class UnauthorizedError(Exception):
        status_code = 401

    mock_client = MagicMock()
    mock_client.interactions.create.side_effect = UnauthorizedError("Invalid API key")

    with pytest.raises(UnauthorizedError, match="Invalid API key"):
        run_triage_agent(
            "Check service",
            client=mock_client,
            model="gemini-4-hydrogen",
            fallback_models=["gemini-3.5-flash-lite"],
        )
    assert mock_client.interactions.create.call_count == 1

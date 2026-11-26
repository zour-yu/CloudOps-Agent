"""Unit tests for CloudOps-Agent tools."""

from unittest.mock import MagicMock, patch

import httpx

from app.tools import check_endpoint_health, parse_log_errors


def test_check_endpoint_health_rejects_invalid_scheme() -> None:
    result = check_endpoint_health("ftp://example.com")
    assert result["healthy"] is False
    assert "http://" in result["error"]


def test_check_endpoint_health_rejects_missing_host() -> None:
    result = check_endpoint_health("https://")
    assert result["healthy"] is False
    assert result["status_code"] is None


def test_check_endpoint_health_success() -> None:
    mock_response = MagicMock(status_code=200)
    with patch("app.tools.httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.get.return_value = mock_response

        result = check_endpoint_health("https://example.com/health")

    assert result["healthy"] is True
    assert result["status_code"] == 200
    assert isinstance(result["latency_ms"], float)


def test_check_endpoint_health_request_error() -> None:
    with patch("app.tools.httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")

        result = check_endpoint_health("http://localhost:9999/health")

    assert result["healthy"] is False
    assert result["status_code"] is None
    assert "Connection refused" in result["error"]


def test_parse_log_errors_extracts_patterns_and_trace() -> None:
    logs = "\n".join(
        [
            "2026-11-26T10:00:01Z INFO Server started on port 8000",
            "2026-11-26T10:01:02Z ERROR Connection timeout to db-1 after 5000ms",
            "2026-11-26T10:01:05Z ERROR Connection timeout to db-2 after 5000ms",
            "Traceback (most recent call last):",
            '  File "app/db.py", line 14, in connect',
            "TimeoutError: database unreachable",
        ]
    )

    result = parse_log_errors(logs)

    assert result["total_lines"] == 6
    assert result["error_line_count"] >= 3
    assert len(result["timestamps"]) == 2
    assert result["top_patterns"][0]["count"] == 2
    assert len(result["stack_traces"]) == 1
    assert "TimeoutError" in result["stack_traces"][0]

"""DevOps tools exposed to the Gemini triage agent."""

from __future__ import annotations

import re
import time
from collections import Counter
from typing import Any
from urllib.parse import urlparse

import httpx

ERROR_LINE_RE = re.compile(
    r"(ERROR|CRITICAL|FATAL|Traceback|Exception|\b5\d{2}\b)",
    re.IGNORECASE,
)
TIMESTAMP_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?\b")
NORMALIZE_NUMBERS_RE = re.compile(r"\b\d+\b")


def check_endpoint_health(url: str, timeout_seconds: float = 5.0) -> dict[str, Any]:
    """Check an HTTP/HTTPS endpoint's status code, health, and response latency."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {
            "url": url,
            "healthy": False,
            "status_code": None,
            "latency_ms": None,
            "error": "URL must be a valid http:// or https:// URL",
        }

    start = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
            response = client.get(url)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        return {
            "url": url,
            "healthy": 200 <= response.status_code < 400,
            "status_code": response.status_code,
            "latency_ms": elapsed_ms,
        }
    except httpx.RequestError as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        return {
            "url": url,
            "healthy": False,
            "status_code": None,
            "latency_ms": elapsed_ms,
            "error": str(exc),
        }


def _extract_stack_traces(lines: list[str], limit: int = 3) -> list[str]:
    """Extract up to `limit` Python stack traces from log lines."""
    traces: list[str] = []
    current: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("Traceback (most recent call last):"):
            if current:
                traces.append("\n".join(current))
            current = [line]
            continue

        if not current:
            continue

        if line.startswith((" ", "\t")):
            current.append(line)
        elif stripped.endswith("Error") or ":" in stripped:
            current.append(line)
            traces.append("\n".join(current))
            current = []
        else:
            traces.append("\n".join(current))
            current = []

    if current:
        traces.append("\n".join(current))
    return traces[:limit]


def parse_log_errors(log_text: str) -> dict[str, Any]:
    """Extract recurring error patterns, timestamps, and stack traces from raw logs."""
    lines = log_text.splitlines()
    error_lines: list[str] = []
    timestamps: list[str] = []
    pattern_counts: Counter[str] = Counter()

    for line in lines:
        if not ERROR_LINE_RE.search(line):
            continue
        stripped = line.strip()
        error_lines.append(stripped)

        ts_match = TIMESTAMP_RE.search(line)
        if ts_match:
            timestamps.append(ts_match.group(0))

        cleaned = TIMESTAMP_RE.sub("<TS>", stripped)
        cleaned = NORMALIZE_NUMBERS_RE.sub("<N>", cleaned)
        pattern_counts[cleaned] += 1

    return {
        "total_lines": len(lines),
        "error_line_count": len(error_lines),
        "timestamps": timestamps[:10],
        "top_patterns": [
            {"pattern": pattern, "count": count}
            for pattern, count in pattern_counts.most_common(5)
        ],
        "stack_traces": _extract_stack_traces(lines),
        "sample_errors": error_lines[:10],
    }


TOOL_REGISTRY = {
    "check_endpoint_health": check_endpoint_health,
    "parse_log_errors": parse_log_errors,
}

TOOL_DECLARATIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "check_endpoint_health",
        "description": "Check an HTTP/HTTPS endpoint's status code, health, and latency in ms.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Full HTTP or HTTPS URL to check.",
                },
            },
            "required": ["url"],
        },
    },
    {
        "type": "function",
        "name": "parse_log_errors",
        "description": "Extract recurring error patterns, timestamps, and stack traces from logs.",
        "parameters": {
            "type": "object",
            "properties": {
                "log_text": {
                    "type": "string",
                    "description": "Raw multi-line application or server logs.",
                },
            },
            "required": ["log_text"],
        },
    },
]

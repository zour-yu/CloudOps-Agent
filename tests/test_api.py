"""Unit tests for the FastAPI endpoints."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "cloudops-agent"


def test_triage_requires_url_or_logs() -> None:
    response = client.post("/triage", json={"target_url": "   ", "logs": ""})
    assert response.status_code == 400


def test_triage_returns_agent_response() -> None:
    fake_result = {
        "summary": "1. Symptoms: 502 error\n2. Root Cause: upstream down",
        "tool_calls": [{"tool": "check_endpoint_health", "arguments": {"url": "http://app/health"}}],
        "interaction_id": "int-123",
    }

    with patch("app.main.run_triage_agent", return_value=fake_result):
        response = client.post(
            "/triage",
            json={"target_url": "http://app/health", "logs": "ERROR 502 Bad Gateway"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["interaction_id"] == "int-123"
    assert "502" in body["summary"]
    assert len(body["tool_calls"]) == 1

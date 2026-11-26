"""FastAPI entrypoint for CloudOps-Agent."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app import __version__
from app.agent import build_triage_prompt, run_triage_agent
from app.config import get_settings

app = FastAPI(
    title="CloudOps-Agent",
    description="Agentic AI Log Triage & Service Health Monitor powered by Gemini.",
    version=__version__,
)


class TriageRequest(BaseModel):
    """Input payload for running an AI-assisted incident triage."""

    target_url: str | None = Field(
        default=None,
        max_length=2048,
        description="Optional HTTP/HTTPS endpoint URL to probe.",
        examples=["http://localhost:8000/health"],
    )
    logs: str | None = Field(
        default=None,
        max_length=200_000,
        description="Optional raw application or server logs to analyze.",
    )
    question: str = Field(
        default="Diagnose the issue and recommend concrete remediation steps.",
        min_length=1,
        max_length=2000,
        description="Triage instruction or question for the agent.",
    )


class TriageResponse(BaseModel):
    """Structured response returned by /triage."""

    summary: str
    tool_calls: list[dict[str, Any]]
    interaction_id: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness and readiness check endpoint."""
    settings = get_settings()
    return {
        "status": "ok",
        "service": "cloudops-agent",
        "version": __version__,
        "environment": settings.app_env,
    }


@app.post("/triage", response_model=TriageResponse)
def triage(request: TriageRequest) -> TriageResponse:
    """Run the CloudOps-Agent against a target URL, logs, or both."""
    target_url = request.target_url.strip() if request.target_url else None
    logs = request.logs.strip() if request.logs else None
    if not target_url and not logs:
        raise HTTPException(
            status_code=400,
            detail="Provide at least 'target_url' or 'logs' to run triage.",
        )

    prompt = build_triage_prompt(
        question=request.question.strip(),
        target_url=target_url,
        logs=logs,
    )

    try:
        result = run_triage_agent(prompt)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Agent execution failed: {exc}") from exc

    return TriageResponse(**result)

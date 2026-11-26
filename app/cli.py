"""CLI interface for running CloudOps-Agent locally."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.agent import build_triage_prompt, run_triage_agent


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="cloudops-agent",
        description="Run AI-assisted health checks and log triage from the terminal.",
    )
    parser.add_argument("--url", help="Service HTTP/HTTPS URL to check.")
    parser.add_argument("--log-file", type=Path, help="Path to a log file to analyze.")
    parser.add_argument(
        "--question",
        default="Diagnose the issue and recommend concrete remediation steps.",
        help="Question or instruction for the triage agent.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Print the full response (including tool calls) as JSON.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    target_url = args.url.strip() if args.url else None
    if not target_url and not args.log_file:
        parser.error("Provide at least --url or --log-file.")

    logs: str | None = None
    if args.log_file:
        if not args.log_file.is_file():
            print(f"Error: log file not found: {args.log_file}", file=sys.stderr)
            return 1
        logs = args.log_file.read_text(encoding="utf-8", errors="replace")

    prompt = build_triage_prompt(
        question=args.question.strip(),
        target_url=target_url,
        logs=logs,
    )
    try:
        result = run_triage_agent(
            prompt,
            on_status=lambda msg: print(msg, file=sys.stderr, flush=True),
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.as_json:
        print(json.dumps(result, indent=2))
    else:
        print(result["summary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

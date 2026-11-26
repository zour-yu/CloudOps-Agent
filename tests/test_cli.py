"""Unit tests for the CloudOps-Agent CLI."""

from pathlib import Path
from unittest.mock import patch

import pytest

from app.cli import main


def test_cli_requires_url_or_log_file() -> None:
    with pytest.raises(SystemExit):
        main([])


def test_cli_runs_with_log_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    log_file = tmp_path / "sample.log"
    log_file.write_text("2026-11-26T10:00:00Z ERROR Connection refused", encoding="utf-8")

    with patch(
        "app.cli.run_triage_agent",
        return_value={"summary": "Service down.", "tool_calls": [], "interaction_id": "int-1"},
    ):
        exit_code = main(["--log-file", str(log_file)])

    assert exit_code == 0
    assert "Service down." in capsys.readouterr().out

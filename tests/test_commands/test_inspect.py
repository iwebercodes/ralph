"""Tests for ralph inspect command."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ralph.cli import app
from ralph.core.run_state import RunState, get_current_log_path, write_run_state

runner = CliRunner()


def test_inspect_not_initialized(temp_project: Path) -> None:
    """Inspect fails when Ralph is not initialized."""
    result = runner.invoke(app, ["inspect"])
    assert result.exit_code == 1
    assert "not initialized" in result.output.lower()


def test_inspect_not_running(initialized_project: Path) -> None:
    """Inspect reports not running when no run state exists."""
    result = runner.invoke(app, ["inspect"])
    assert result.exit_code == 0
    assert "not running" in result.output.lower()


def test_inspect_running(initialized_project: Path) -> None:
    """Inspect reports running with details."""
    state = RunState(
        pid=os.getpid(),
        started_at="2025-01-19T14:30:00+00:00",
        iteration=2,
        max_iterations=20,
        agent="Codex",
        agent_started_at="2025-01-19T14:32:15+00:00",
    )
    write_run_state(state, initialized_project)

    result = runner.invoke(app, ["inspect"])
    assert result.exit_code == 0
    assert "ralph is running" in result.output.lower()
    assert "codex" in result.output.lower()
    assert "2/20" in result.output


def test_inspect_json(initialized_project: Path) -> None:
    """Inspect JSON output includes run details."""
    state = RunState(
        pid=os.getpid(),
        started_at="2025-01-19T14:30:00+00:00",
        iteration=1,
        max_iterations=20,
        agent="Claude",
        agent_started_at="2025-01-19T14:30:10+00:00",
    )
    write_run_state(state, initialized_project)

    result = runner.invoke(app, ["inspect", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["running"] is True
    assert data["pid"] == os.getpid()
    assert data["agent"] == "Claude"


def test_inspect_stale_pid(initialized_project: Path) -> None:
    """Inspect reports not running for stale PID."""
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.1)"])
    process.wait()
    time.sleep(0.05)
    state = RunState(
        pid=process.pid,
        started_at="2025-01-19T14:30:00+00:00",
        iteration=1,
        max_iterations=20,
        agent="Codex",
        agent_started_at="2025-01-19T14:30:10+00:00",
    )
    write_run_state(state, initialized_project)

    result = runner.invoke(app, ["inspect"])
    assert result.exit_code == 0
    assert "not running" in result.output.lower()


def test_inspect_follow_tails_log(
    initialized_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Inspect --follow tails current log."""
    state = RunState(
        pid=os.getpid(),
        started_at="2025-01-19T14:30:00+00:00",
        iteration=1,
        max_iterations=20,
        agent="Codex",
        agent_started_at="2025-01-19T14:30:10+00:00",
    )
    write_run_state(state, initialized_project)

    from ralph.commands import inspect as inspect_cmd

    called: dict[str, Path] = {}

    def fake_tail(path: Path) -> None:
        called["path"] = path

    monkeypatch.setattr(inspect_cmd, "_tail_current_log", fake_tail)

    result = runner.invoke(app, ["inspect", "--follow"])
    assert result.exit_code == 0
    assert called["path"] == get_current_log_path(initialized_project)

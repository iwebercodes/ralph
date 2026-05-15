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


def test_inspect_not_running_json(initialized_project: Path) -> None:
    """Inspect JSON output for not running state."""
    result = runner.invoke(app, ["inspect", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data == {"running": False}


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
    assert data["iteration"] == 1
    assert data["max_iterations"] == 20
    assert data["current_agent"] == "claude"
    assert "status" in data
    assert "runtime" in data


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


class TestInspectHelpers:
    """Tests for inspect helper functions."""

    def test_format_duration_hours(self) -> None:
        """Test _format_duration with hours."""
        from ralph.commands.inspect import _format_duration

        assert _format_duration(3661) == "1h 1m 1s"
        assert _format_duration(7261) == "2h 1m 1s"
        assert _format_duration(0) == "0s"
        assert _format_duration(61) == "1m 1s"

    def test_format_duration_negative(self) -> None:
        """Test _format_duration clamps negative values."""
        from ralph.commands.inspect import _format_duration

        assert _format_duration(-10) == "0s"

    def test_seconds_since_bad_timestamp(self) -> None:
        """Test _seconds_since with unparseable timestamp."""
        from ralph.commands.inspect import _seconds_since

        assert _seconds_since("not-a-date") is None
        assert _seconds_since("") is None

    def test_seconds_since_timezone_naive(self) -> None:
        """Test _seconds_since with timezone-naive timestamp."""
        from ralph.commands.inspect import _seconds_since

        # Naive timestamps should be treated as UTC
        result = _seconds_since("2025-01-19T14:30:00")
        assert result is not None
        assert result > 0  # Should be positive (time since then)

    def test_tail_current_log_with_tail_available(
        self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test _tail_current_log when tail is available on PATH."""
        from unittest.mock import MagicMock, patch

        mock_proc = MagicMock()
        mock_proc.returncode = 0

        def fake_which(name: str) -> str | None:
            if name == "tail":
                return "/usr/bin/tail"
            return None

        log_path = get_current_log_path(initialized_project)

        with (
            patch("shutil.which", fake_which),
            patch("subprocess.run", return_value=mock_proc) as mock_run,
        ):
            from ralph.commands.inspect import _tail_current_log

            _tail_current_log(log_path)

        # subprocess.run should have been called with tail -f <path>
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "tail" in call_args[0]
        assert str(log_path) in call_args

    def test_tail_current_log_creates_parent(
        self, temp_project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test _tail_current_log creates parent directory if missing.

        We mock shutil.which to return a fake tail path so subprocess.run
        is called instead of entering the blocking while loop.
        """
        from unittest.mock import MagicMock, patch

        log_path = temp_project / ".ralph" / "nested" / "deep" / "current.log"
        assert not log_path.exists()

        mock_proc = MagicMock()
        mock_proc.returncode = 0

        def fake_which(name: str) -> str | None:
            if name == "tail":
                return "/usr/bin/tail"
            return None

        with patch("shutil.which", fake_which), patch("subprocess.run", return_value=mock_proc):
            from ralph.commands.inspect import _tail_current_log

            _tail_current_log(log_path)

        # write_text in the fallback creates parent dirs + empty file
        assert log_path.parent.exists()
        assert log_path.exists()

    def test_inspect_not_running_with_follow(
        self, initialized_project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Inspect --follow on not-running state tails the log."""
        from ralph.commands import inspect as inspect_cmd

        called: dict[str, Path] = {}

        def fake_tail(path: Path) -> None:
            called["path"] = path

        monkeypatch.setattr(inspect_cmd, "_tail_current_log", fake_tail)

        result = runner.invoke(app, ["inspect", "--follow"])
        assert result.exit_code == 0
        assert "not running" in result.output.lower()
        assert called["path"] == get_current_log_path(initialized_project)

"""Tests for ralph status command."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from ralph.cli import app
from ralph.core.state import Status, write_done_count, write_iteration, write_status

runner = CliRunner()


def test_status_not_initialized(temp_project: Path) -> None:
    """Test status fails when not initialized."""
    result = runner.invoke(app, ["status"])

    assert result.exit_code == 1
    assert "not initialized" in result.output


def test_status_basic(initialized_project: Path) -> None:
    """Test basic status output."""
    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    # Non-TTY mode uses [ralph] prefix format
    assert "[ralph] Status:" in result.output
    assert "iteration" in result.output
    assert "IDLE" in result.output


def test_status_shows_current_state(initialized_project: Path) -> None:
    """Test status shows current state values."""
    write_iteration(5, initialized_project)
    write_done_count(2, initialized_project)
    write_status(Status.DONE, initialized_project)

    result = runner.invoke(app, ["status"])

    assert "5" in result.output
    assert "DONE" in result.output
    assert "2" in result.output


def test_status_shows_goal_preview(project_with_prompt: Path) -> None:
    """Test status shows goal preview from PROMPT.md."""
    result = runner.invoke(app, ["status"])

    # Non-TTY mode uses [ralph] prefix format
    assert "[ralph] Goal:" in result.output
    assert "Test goal content" in result.output


def test_status_json_output(initialized_project: Path) -> None:
    """Test status --json output."""
    write_iteration(3, initialized_project)
    write_status(Status.ROTATE, initialized_project)

    result = runner.invoke(app, ["status", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["initialized"] is True
    assert data["iteration"] == 3
    assert data["status"] == "ROTATE"


def test_status_json_not_initialized(temp_project: Path) -> None:
    """Test status --json when not initialized."""
    result = runner.invoke(app, ["status", "--json"])

    assert result.exit_code == 1
    data = json.loads(result.output)
    assert data["initialized"] is False

"""Tests for ralph history command."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from ralph.cli import app
from ralph.core.state import write_history

runner = CliRunner()


def test_history_not_initialized(temp_project: Path) -> None:
    """Test history fails when not initialized."""
    result = runner.invoke(app, ["history"])

    assert result.exit_code == 1
    assert "not initialized" in result.output


def test_history_no_logs(initialized_project: Path) -> None:
    """Test history fails when no logs exist."""
    result = runner.invoke(app, ["history"])

    assert result.exit_code == 1
    assert "No history" in result.output


def test_history_shows_most_recent(initialized_project: Path) -> None:
    """Test history shows most recent rotation by default."""
    write_history(1, "Rotation 1 content", initialized_project)
    write_history(2, "Rotation 2 content", initialized_project)

    result = runner.invoke(app, ["history"])

    assert result.exit_code == 0
    assert "Rotation 2" in result.output
    assert "Rotation 2 content" in result.output


def test_history_specific_rotation(initialized_project: Path) -> None:
    """Test viewing a specific rotation."""
    write_history(1, "Rotation 1 specific content", initialized_project)
    write_history(2, "Rotation 2 content", initialized_project)

    result = runner.invoke(app, ["history", "1"])

    assert result.exit_code == 0
    assert "Rotation 1" in result.output
    assert "Rotation 1 specific content" in result.output


def test_history_nonexistent_rotation(initialized_project: Path) -> None:
    """Test viewing nonexistent rotation fails."""
    write_history(1, "Content", initialized_project)

    result = runner.invoke(app, ["history", "99"])

    assert result.exit_code == 1
    assert "not found" in result.output


def test_history_list(initialized_project: Path) -> None:
    """Test history --list shows all rotations."""
    log1 = """================================================================================
RALPH ROTATION 1 - 2024-01-15T10:00:00Z
================================================================================

--- STATUS ---
Signal: ROTATE
Files Changed: 3
"""
    log2 = """================================================================================
RALPH ROTATION 2 - 2024-01-15T10:05:00Z
================================================================================

--- STATUS ---
Signal: DONE
Files Changed: 0
"""
    write_history(1, log1, initialized_project)
    write_history(2, log2, initialized_project)

    result = runner.invoke(app, ["history", "--list"])

    assert result.exit_code == 0
    # Non-TTY mode uses [ralph] prefix format
    assert "[ralph]" in result.output
    assert "1." in result.output
    assert "2." in result.output
    assert "ROTATE" in result.output
    assert "DONE" in result.output


def test_history_tail(initialized_project: Path) -> None:
    """Test history --tail limits output."""
    content = "\n".join([f"Line {i}" for i in range(100)])
    write_history(1, content, initialized_project)

    result = runner.invoke(app, ["history", "--tail", "5"])

    assert result.exit_code == 0
    # Should have header + separator + 5 lines
    assert "Line 99" in result.output
    assert "Line 95" in result.output

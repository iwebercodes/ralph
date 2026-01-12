"""Tests for ralph reset command."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from ralph.cli import app
from ralph.core.state import (
    GUARDRAILS_TEMPLATE,
    HANDOFF_TEMPLATE,
    Status,
    read_done_count,
    read_guardrails,
    read_handoff,
    read_iteration,
    read_status,
    write_done_count,
    write_guardrails,
    write_handoff,
    write_history,
    write_iteration,
    write_status,
)

runner = CliRunner()


def test_reset_not_initialized(temp_project: Path) -> None:
    """Test reset fails when not initialized."""
    result = runner.invoke(app, ["reset"])

    assert result.exit_code == 1
    assert "not initialized" in result.output


def test_reset_clears_state(initialized_project: Path) -> None:
    """Test reset clears iteration and done_count."""
    write_iteration(5, initialized_project)
    write_done_count(2, initialized_project)
    write_status(Status.DONE, initialized_project)

    result = runner.invoke(app, ["reset"])

    assert result.exit_code == 0
    assert read_iteration(initialized_project) == 0
    assert read_done_count(initialized_project) == 0
    assert read_status(initialized_project) == Status.IDLE


def test_reset_clears_handoff(initialized_project: Path) -> None:
    """Test reset clears handoff to template."""
    write_handoff("Custom handoff content", initialized_project)

    runner.invoke(app, ["reset"])

    assert read_handoff(initialized_project) == HANDOFF_TEMPLATE.strip()


def test_reset_clears_guardrails_by_default(initialized_project: Path) -> None:
    """Test reset clears guardrails by default."""
    write_guardrails("# Custom guardrails\n\n- Rule 1", initialized_project)

    runner.invoke(app, ["reset"])

    assert read_guardrails(initialized_project) == GUARDRAILS_TEMPLATE.strip()


def test_reset_keeps_guardrails(initialized_project: Path) -> None:
    """Test reset --keep-guardrails preserves guardrails."""
    custom_guardrails = "# Custom guardrails\n\n- Rule 1"
    write_guardrails(custom_guardrails, initialized_project)

    result = runner.invoke(app, ["reset", "--keep-guardrails"])

    assert result.exit_code == 0
    assert read_guardrails(initialized_project) == custom_guardrails
    assert "preserved" in result.output


def test_reset_clears_history_by_default(initialized_project: Path) -> None:
    """Test reset clears history by default."""
    write_history(1, "Log content", initialized_project)

    history_dir = initialized_project / ".ralph" / "history"
    assert len(list(history_dir.glob("*.log"))) == 1

    runner.invoke(app, ["reset"])

    assert len(list(history_dir.glob("*.log"))) == 0


def test_reset_keeps_history(initialized_project: Path) -> None:
    """Test reset --keep-history preserves history."""
    write_history(1, "Log content", initialized_project)

    result = runner.invoke(app, ["reset", "--keep-history"])

    assert result.exit_code == 0
    history_dir = initialized_project / ".ralph" / "history"
    assert len(list(history_dir.glob("*.log"))) == 1
    assert "preserved" in result.output


def test_reset_output_shows_status(initialized_project: Path) -> None:
    """Test reset output shows what was done."""
    result = runner.invoke(app, ["reset"])

    assert "Reset complete" in result.output
    assert "Iteration: 0" in result.output
    assert "Status: IDLE" in result.output

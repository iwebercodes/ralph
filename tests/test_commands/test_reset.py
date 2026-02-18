"""Tests for ralph reset command."""

from __future__ import annotations

import os
from pathlib import Path

from typer.testing import CliRunner

from ralph.cli import app
from ralph.core.run_state import RunState, write_run_state
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
    """Test reset clears iteration and status, but preserves done_count."""
    write_iteration(5, initialized_project)
    write_done_count(2, initialized_project)
    write_status(Status.DONE, initialized_project)

    result = runner.invoke(app, ["reset"])

    assert result.exit_code == 0
    assert read_iteration(initialized_project) == 0
    assert read_done_count(initialized_project) == 2  # Preserved by default
    assert read_status(initialized_project) == Status.IDLE


def test_reset_preserves_handoff_by_default(initialized_project: Path) -> None:
    """Test reset preserves handoff by default."""
    custom_handoff = "Custom handoff content"
    write_handoff(custom_handoff, initialized_project)

    runner.invoke(app, ["reset"])

    assert read_handoff(initialized_project) == custom_handoff


def test_reset_preserves_guardrails_by_default(initialized_project: Path) -> None:
    """Test reset preserves guardrails by default."""
    custom_guardrails = "# Custom guardrails\n\n- Rule 1"
    write_guardrails(custom_guardrails, initialized_project)

    runner.invoke(app, ["reset"])

    assert read_guardrails(initialized_project) == custom_guardrails


def test_reset_resets_guardrails(initialized_project: Path) -> None:
    """Test reset --reset-guardrails resets guardrails to template."""
    custom_guardrails = "# Custom guardrails\n\n- Rule 1"
    write_guardrails(custom_guardrails, initialized_project)

    result = runner.invoke(app, ["reset", "--reset-guardrails"])

    assert result.exit_code == 0
    assert read_guardrails(initialized_project) == GUARDRAILS_TEMPLATE.strip()
    assert "reset to template" in result.output


def test_reset_preserves_history_by_default(initialized_project: Path) -> None:
    """Test reset preserves history by default."""
    write_history(1, "Log content", initialized_project)

    history_dir = initialized_project / ".ralph" / "history"
    assert len(list(history_dir.glob("*.log"))) == 1

    runner.invoke(app, ["reset"])

    assert len(list(history_dir.glob("*.log"))) == 1


def test_reset_clears_history(initialized_project: Path) -> None:
    """Test reset --reset-history clears history."""
    write_history(1, "Log content", initialized_project)

    result = runner.invoke(app, ["reset", "--reset-history"])

    assert result.exit_code == 0
    history_dir = initialized_project / ".ralph" / "history"
    assert len(list(history_dir.glob("*.log"))) == 0
    assert "cleared" in result.output


def test_reset_output_shows_status(initialized_project: Path) -> None:
    """Test reset output shows what was done."""
    result = runner.invoke(app, ["reset"])

    assert "Reset complete" in result.output
    assert "Iteration: 0" in result.output
    assert "Status: IDLE" in result.output


def test_reset_preserves_counter_by_default(initialized_project: Path) -> None:
    """Test reset preserves done_count by default."""
    write_done_count(5, initialized_project)

    result = runner.invoke(app, ["reset"])

    assert result.exit_code == 0
    assert read_done_count(initialized_project) == 5  # Should be preserved
    assert "Counters: preserved" in result.output


def test_reset_resets_counter(initialized_project: Path) -> None:
    """Test reset --reset-counter resets done_count to 0."""
    write_done_count(5, initialized_project)

    result = runner.invoke(app, ["reset", "--reset-counter"])

    assert result.exit_code == 0
    assert read_done_count(initialized_project) == 0
    assert "Counters: reset to 0" in result.output


def test_reset_resets_handoffs(initialized_project: Path) -> None:
    """Test reset --reset-handoffs resets all handoff files."""
    # Create a handoff in the handoffs directory
    handoffs_dir = initialized_project / ".ralph" / "handoffs"
    handoffs_dir.mkdir(parents=True, exist_ok=True)
    handoff_file = handoffs_dir / "test.spec-abcdef.md"
    handoff_file.write_text("Custom handoff content")

    result = runner.invoke(app, ["reset", "--reset-handoffs"])

    assert result.exit_code == 0
    assert handoff_file.exists()
    assert handoff_file.read_text() == HANDOFF_TEMPLATE
    assert read_handoff(initialized_project) == HANDOFF_TEMPLATE.strip()
    assert "Handoffs: reset to template" in result.output


def test_reset_fails_when_running(initialized_project: Path) -> None:
    """Reset fails when Ralph run-state indicates an active process."""
    write_run_state(
        RunState(
            pid=os.getpid(),
            started_at="2025-01-19T14:30:00+00:00",
            iteration=1,
            max_iterations=20,
            agent="Codex",
            agent_started_at="2025-01-19T14:30:10+00:00",
        ),
        initialized_project,
    )

    result = runner.invoke(app, ["reset"])
    assert result.exit_code == 1
    assert "currently running" in result.output.lower()


def test_reset_combined_flags(initialized_project: Path) -> None:
    """Combined reset flags should work together."""
    write_done_count(4, initialized_project)
    write_guardrails("# Custom", initialized_project)
    write_history(1, "Log content", initialized_project)
    write_handoff("Custom handoff", initialized_project)

    result = runner.invoke(
        app,
        [
            "reset",
            "--reset-counter",
            "--reset-guardrails",
            "--reset-history",
            "--reset-handoffs",
        ],
    )

    assert result.exit_code == 0
    assert read_done_count(initialized_project) == 0
    assert read_guardrails(initialized_project) == GUARDRAILS_TEMPLATE.strip()
    assert read_handoff(initialized_project) == HANDOFF_TEMPLATE.strip()
    assert len(list((initialized_project / ".ralph" / "history").glob("*.log"))) == 0

"""Tests for ralph init command."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from ralph.cli import app
from ralph.core.state import RALPH_DIR, Status, is_initialized, read_status

runner = CliRunner()


def test_init_creates_directory(temp_project: Path) -> None:
    """Test init creates .ralph directory."""
    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0
    assert is_initialized(temp_project)
    assert (temp_project / RALPH_DIR).exists()


def test_init_creates_state_files(temp_project: Path) -> None:
    """Test init creates all state files."""
    runner.invoke(app, ["init"])

    ralph_dir = temp_project / RALPH_DIR
    assert (ralph_dir / "status").exists()
    assert (ralph_dir / "iteration").exists()
    assert (ralph_dir / "done_count").exists()
    assert (ralph_dir / "handoff.md").exists()
    assert (ralph_dir / "guardrails.md").exists()
    assert (ralph_dir / "history").exists()


def test_init_creates_prompt_md(temp_project: Path) -> None:
    """Test init creates PROMPT.md template."""
    result = runner.invoke(app, ["init"])

    prompt_file = temp_project / "PROMPT.md"
    assert prompt_file.exists()
    assert "Created PROMPT.md" in result.output


def test_init_does_not_overwrite_prompt_md(temp_project: Path) -> None:
    """Test init preserves existing PROMPT.md."""
    prompt_file = temp_project / "PROMPT.md"
    prompt_file.write_text("My existing goal")

    result = runner.invoke(app, ["init"])

    assert prompt_file.read_text() == "My existing goal"
    assert "Created PROMPT.md" not in result.output


def test_init_fails_if_exists(initialized_project: Path) -> None:
    """Test init fails if .ralph already exists."""
    result = runner.invoke(app, ["init"])

    assert result.exit_code == 1
    assert "already exists" in result.output


def test_init_force_overwrites(initialized_project: Path) -> None:
    """Test init --force overwrites existing .ralph."""
    # Modify state
    from ralph.core.state import write_iteration

    write_iteration(5, initialized_project)

    result = runner.invoke(app, ["init", "--force"])

    assert result.exit_code == 0
    assert "Reinitialized" in result.output

    # Check state was reset
    from ralph.core.state import read_iteration

    assert read_iteration(initialized_project) == 0


def test_init_sets_idle_status(temp_project: Path) -> None:
    """Test init sets status to IDLE."""
    runner.invoke(app, ["init"])

    assert read_status(temp_project) == Status.IDLE


def test_init_shows_next_steps(temp_project: Path) -> None:
    """Test init shows next steps."""
    result = runner.invoke(app, ["init"])

    assert "Next steps" in result.output
    assert "PROMPT.md" in result.output
    assert "ralph run" in result.output

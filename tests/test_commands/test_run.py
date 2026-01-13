"""Tests for ralph run command."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from typer.testing import CliRunner

if TYPE_CHECKING:
    import pytest

    from tests.conftest import MockClaude

from ralph.cli import app
from ralph.core.state import read_iteration, write_iteration

runner = CliRunner()


def test_run_not_initialized(temp_project: Path) -> None:
    """Test run fails when not initialized."""
    result = runner.invoke(app, ["run"])

    assert result.exit_code == 1
    assert "not initialized" in result.output


def test_run_no_prompt(initialized_project: Path) -> None:
    """Test run fails when PROMPT.md is missing."""
    result = runner.invoke(app, ["run"])

    assert result.exit_code == 1
    assert "PROMPT.md" in result.output


def test_run_empty_prompt(initialized_project: Path) -> None:
    """Test run fails when PROMPT.md is empty."""
    (initialized_project / "PROMPT.md").write_text("")

    result = runner.invoke(app, ["run"])

    assert result.exit_code == 1
    assert "empty" in result.output.lower()


def test_run_no_claude(project_with_prompt: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test run fails when claude CLI is not available."""
    # Remove claude from PATH by setting empty PATH
    monkeypatch.setenv("PATH", "/nonexistent")

    result = runner.invoke(app, ["run"])

    assert result.exit_code == 1
    assert "claude" in result.output.lower()


def test_run_single_iteration(
    project_with_prompt: Path,
    mock_claude: MockClaude,
) -> None:
    """Test run executes a single iteration."""
    mock_claude.set_responses(
        [
            {"status": "DONE", "output": "First iteration done", "changes": []},
            {"status": "DONE", "output": "Review 1", "changes": []},
            {"status": "DONE", "output": "Review 2", "changes": []},
        ]
    )

    result = runner.invoke(app, ["run", "--max", "10"])

    assert result.exit_code == 0
    assert "Goal achieved" in result.output
    assert read_iteration(project_with_prompt) == 3


def test_run_rotate_then_done(
    project_with_prompt: Path,
    mock_claude: MockClaude,
) -> None:
    """Test run handles ROTATE then DONE signals."""
    mock_claude.set_responses(
        [
            {"status": "ROTATE", "output": "Making progress", "changes": ["file1.py"]},
            {"status": "DONE", "output": "Finished", "changes": []},
            {"status": "DONE", "output": "Review 1", "changes": []},
            {"status": "DONE", "output": "Review 2", "changes": []},
        ]
    )

    result = runner.invoke(app, ["run", "--max", "10"])

    assert result.exit_code == 0
    assert read_iteration(project_with_prompt) == 4


def test_run_stuck_exits(
    project_with_prompt: Path,
    mock_claude: MockClaude,
) -> None:
    """Test run exits with code 2 on STUCK signal."""
    mock_claude.set_responses(
        [
            {"status": "STUCK", "output": "I'm blocked", "changes": []},
        ]
    )

    result = runner.invoke(app, ["run", "--max", "10"])

    assert result.exit_code == 2
    assert "stuck" in result.output.lower()


def test_run_max_iterations(
    project_with_prompt: Path,
    mock_claude: MockClaude,
) -> None:
    """Test run stops at max iterations."""
    # All ROTATE signals to keep going
    mock_claude.set_responses(
        [
            {"status": "ROTATE", "output": "Still working", "changes": [f"file{i}.py"]}
            for i in range(5)
        ]
    )

    result = runner.invoke(app, ["run", "--max", "3"])

    assert result.exit_code == 3
    assert "max iterations" in result.output.lower()
    assert read_iteration(project_with_prompt) == 3


def test_run_done_with_changes_resets(
    project_with_prompt: Path,
    mock_claude: MockClaude,
) -> None:
    """Test DONE with changes resets verification count."""
    mock_claude.set_responses(
        [
            {"status": "DONE", "output": "Done but changed", "changes": ["file.py"]},
            {"status": "DONE", "output": "Really done", "changes": []},
            {"status": "DONE", "output": "Review 1", "changes": []},
            {"status": "DONE", "output": "Review 2", "changes": []},
        ]
    )

    result = runner.invoke(app, ["run", "--max", "10"])

    assert result.exit_code == 0
    # Took 4 iterations: 1 DONE with changes, then 3 consecutive DONEs
    assert read_iteration(project_with_prompt) == 4


def test_run_creates_history(
    project_with_prompt: Path,
    mock_claude: MockClaude,
) -> None:
    """Test run creates history log files."""
    mock_claude.set_responses(
        [
            {"status": "DONE", "output": "Done", "changes": []},
            {"status": "DONE", "output": "Review", "changes": []},
            {"status": "DONE", "output": "Review", "changes": []},
        ]
    )

    runner.invoke(app, ["run", "--max", "10"])

    history_dir = project_with_prompt / ".ralph" / "history"
    log_files = list(history_dir.glob("*.log"))
    assert len(log_files) == 3


def test_run_resume_from_previous(
    project_with_prompt: Path,
    mock_claude: MockClaude,
) -> None:
    """Test run resumes from previous iteration count."""
    write_iteration(5, project_with_prompt)

    mock_claude.set_responses(
        [
            {"status": "DONE", "output": "Done", "changes": []},
            {"status": "DONE", "output": "Review", "changes": []},
            {"status": "DONE", "output": "Review", "changes": []},
        ]
    )

    result = runner.invoke(app, ["run", "--max", "20"])

    assert result.exit_code == 0
    assert read_iteration(project_with_prompt) == 8

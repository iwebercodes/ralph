"""Tests for state management."""

from __future__ import annotations

from pathlib import Path

from ralph.core.state import (
    GUARDRAILS_TEMPLATE,
    HANDOFF_TEMPLATE,
    Status,
    is_initialized,
    read_done_count,
    read_guardrails,
    read_handoff,
    read_iteration,
    read_prompt_md,
    read_state,
    read_status,
    write_done_count,
    write_guardrails,
    write_handoff,
    write_iteration,
    write_status,
)


def test_is_initialized_false(temp_project: Path) -> None:
    """Test is_initialized returns False when not initialized."""
    assert is_initialized(temp_project) is False


def test_is_initialized_true(initialized_project: Path) -> None:
    """Test is_initialized returns True when initialized."""
    assert is_initialized(initialized_project) is True


def test_read_write_iteration(initialized_project: Path) -> None:
    """Test reading and writing iteration number."""
    write_iteration(5, initialized_project)
    assert read_iteration(initialized_project) == 5

    write_iteration(0, initialized_project)
    assert read_iteration(initialized_project) == 0


def test_read_iteration_default(initialized_project: Path) -> None:
    """Test reading iteration returns 0 when file is missing or invalid."""
    # Delete the iteration file
    (initialized_project / ".ralph" / "iteration").unlink()
    assert read_iteration(initialized_project) == 0


def test_read_write_done_count(initialized_project: Path) -> None:
    """Test reading and writing done count."""
    write_done_count(2, initialized_project)
    assert read_done_count(initialized_project) == 2


def test_read_write_status(initialized_project: Path) -> None:
    """Test reading and writing status."""
    for status in Status:
        write_status(status, initialized_project)
        assert read_status(initialized_project) == status


def test_read_status_invalid(initialized_project: Path) -> None:
    """Test reading status with invalid value defaults to CONTINUE."""
    status_file = initialized_project / ".ralph" / "status"
    status_file.write_text("INVALID")
    assert read_status(initialized_project) == Status.CONTINUE


def test_read_status_case_insensitive(initialized_project: Path) -> None:
    """Test reading status is case insensitive."""
    status_file = initialized_project / ".ralph" / "status"
    status_file.write_text("done")
    assert read_status(initialized_project) == Status.DONE


def test_read_state(initialized_project: Path) -> None:
    """Test reading complete state."""
    write_iteration(3, initialized_project)
    write_done_count(1, initialized_project)
    write_status(Status.ROTATE, initialized_project)

    state = read_state(initialized_project)
    assert state.iteration == 3
    assert state.done_count == 1
    assert state.status == Status.ROTATE


def test_read_write_handoff(initialized_project: Path) -> None:
    """Test reading and writing handoff content."""
    content = "# Custom handoff\n\nSome progress notes."
    write_handoff(content, initialized_project)
    assert read_handoff(initialized_project) == content


def test_read_handoff_default(initialized_project: Path) -> None:
    """Test reading handoff returns template when file missing."""
    (initialized_project / ".ralph" / "handoff.md").unlink()
    assert read_handoff(initialized_project) == HANDOFF_TEMPLATE


def test_read_write_guardrails(initialized_project: Path) -> None:
    """Test reading and writing guardrails content."""
    content = "# Guardrails\n\n- Never do X"
    write_guardrails(content, initialized_project)
    assert read_guardrails(initialized_project) == content


def test_read_guardrails_default(initialized_project: Path) -> None:
    """Test reading guardrails returns template when file missing."""
    (initialized_project / ".ralph" / "guardrails.md").unlink()
    assert read_guardrails(initialized_project) == GUARDRAILS_TEMPLATE


def test_read_prompt_md_exists(project_with_prompt: Path) -> None:
    """Test reading PROMPT.md when it exists."""
    content = read_prompt_md(project_with_prompt)
    assert content is not None
    assert "Test goal content" in content


def test_read_prompt_md_missing(initialized_project: Path) -> None:
    """Test reading PROMPT.md when missing."""
    assert read_prompt_md(initialized_project) is None


def test_read_prompt_md_empty(initialized_project: Path) -> None:
    """Test reading empty PROMPT.md returns None."""
    (initialized_project / "PROMPT.md").write_text("")
    assert read_prompt_md(initialized_project) is None


def test_read_prompt_md_whitespace_only(initialized_project: Path) -> None:
    """Test reading whitespace-only PROMPT.md returns None."""
    (initialized_project / "PROMPT.md").write_text("   \n  \n   ")
    assert read_prompt_md(initialized_project) is None

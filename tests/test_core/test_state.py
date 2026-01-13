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


# =============================================================================
# Cross-Platform File Handling Tests
# =============================================================================


def test_file_with_windows_line_endings(initialized_project: Path) -> None:
    """Test reading files with Windows line endings (CRLF)."""
    content_with_crlf = "# Handoff\r\n\r\n## Completed\r\n\r\nTask 1\r\nTask 2"
    handoff_path = initialized_project / ".ralph" / "handoff.md"
    handoff_path.write_bytes(content_with_crlf.encode("utf-8"))

    result = read_handoff(initialized_project)
    # read_file uses .strip() which removes trailing whitespace
    # Content should be readable
    assert "Handoff" in result
    assert "Completed" in result
    assert "Task 1" in result


def test_file_with_unix_line_endings(initialized_project: Path) -> None:
    """Test reading files with Unix line endings (LF)."""
    content_with_lf = "# Guardrails\n\n- Rule 1\n- Rule 2"
    guardrails_path = initialized_project / ".ralph" / "guardrails.md"
    guardrails_path.write_bytes(content_with_lf.encode("utf-8"))

    result = read_guardrails(initialized_project)
    assert "Guardrails" in result
    assert "Rule 1" in result
    assert "Rule 2" in result


def test_file_with_mixed_line_endings(initialized_project: Path) -> None:
    """Test reading files with mixed line endings (CR, LF, CRLF)."""
    # Mix of line ending styles that might occur in files edited across platforms
    content_mixed = "# Handoff\r\n\n## Completed\r\nTask\n"
    handoff_path = initialized_project / ".ralph" / "handoff.md"
    handoff_path.write_bytes(content_mixed.encode("utf-8"))

    result = read_handoff(initialized_project)
    assert "Handoff" in result
    assert "Completed" in result
    assert "Task" in result


def test_file_with_utf8_bom(initialized_project: Path) -> None:
    """Test reading files with UTF-8 BOM (common on Windows)."""
    # UTF-8 BOM is \xef\xbb\xbf
    bom = b"\xef\xbb\xbf"
    content = "# Guardrails\n\n- Don't break things"
    guardrails_path = initialized_project / ".ralph" / "guardrails.md"
    guardrails_path.write_bytes(bom + content.encode("utf-8"))

    result = read_guardrails(initialized_project)
    # Even with BOM, content should be readable
    assert "Guardrails" in result
    assert "Don't break things" in result


def test_file_with_unicode_content(initialized_project: Path) -> None:
    """Test reading files with various Unicode content."""
    content = (
        "# Handoff 📋\n\n## Complété ✅\n\n- Täsk with ümläuts\n- 日本語テキスト\n- Emoji: 🚀 🎉 💻"
    )
    handoff_path = initialized_project / ".ralph" / "handoff.md"
    handoff_path.write_text(content, encoding="utf-8")

    result = read_handoff(initialized_project)
    assert "📋" in result
    assert "✅" in result
    assert "ümläuts" in result
    assert "日本語テキスト" in result
    assert "🚀" in result


def test_prompt_md_with_windows_line_endings(initialized_project: Path) -> None:
    """Test reading PROMPT.md with Windows line endings."""
    content = "# Goal\r\n\r\nBuild a feature\r\n\r\n# Success Criteria\r\n\r\n- [ ] Done"
    prompt_path = initialized_project / "PROMPT.md"
    prompt_path.write_bytes(content.encode("utf-8"))

    result = read_prompt_md(initialized_project)
    assert result is not None
    assert "Goal" in result
    assert "Build a feature" in result


def test_prompt_md_with_utf8_bom(initialized_project: Path) -> None:
    """Test reading PROMPT.md with UTF-8 BOM."""
    bom = b"\xef\xbb\xbf"
    content = "# Goal\n\nTest content"
    prompt_path = initialized_project / "PROMPT.md"
    prompt_path.write_bytes(bom + content.encode("utf-8"))

    result = read_prompt_md(initialized_project)
    assert result is not None
    assert "Test content" in result


# =============================================================================
# Edge Case Tests
# =============================================================================


def test_read_handoff_empty_file(initialized_project: Path) -> None:
    """Test reading empty handoff.md returns default template."""
    handoff_path = initialized_project / ".ralph" / "handoff.md"
    handoff_path.write_text("")

    result = read_handoff(initialized_project)
    # Empty file should return empty string after strip, but read_file returns default for empty
    assert result == ""  # Empty string because file exists but is empty


def test_read_guardrails_empty_file(initialized_project: Path) -> None:
    """Test reading empty guardrails.md returns empty string."""
    guardrails_path = initialized_project / ".ralph" / "guardrails.md"
    guardrails_path.write_text("")

    result = read_guardrails(initialized_project)
    assert result == ""


def test_read_handoff_whitespace_only(initialized_project: Path) -> None:
    """Test reading whitespace-only handoff.md returns empty string after strip."""
    handoff_path = initialized_project / ".ralph" / "handoff.md"
    handoff_path.write_text("   \n\t\n   ")

    result = read_handoff(initialized_project)
    assert result == ""  # strip() removes all whitespace


def test_read_guardrails_whitespace_only(initialized_project: Path) -> None:
    """Test reading whitespace-only guardrails.md returns empty string after strip."""
    guardrails_path = initialized_project / ".ralph" / "guardrails.md"
    guardrails_path.write_text("   \n\t\n   ")

    result = read_guardrails(initialized_project)
    assert result == ""


def test_large_file_content(initialized_project: Path) -> None:
    """Test reading large file content (>50KB)."""
    # Create content larger than 50KB
    large_content = "# Large Handoff\n\n" + ("A" * 1000 + "\n") * 60  # ~60KB
    assert len(large_content) > 50 * 1024  # Verify it's over 50KB

    handoff_path = initialized_project / ".ralph" / "handoff.md"
    handoff_path.write_text(large_content)

    result = read_handoff(initialized_project)
    assert "Large Handoff" in result
    assert len(result) > 50 * 1024


def test_file_with_curly_braces(initialized_project: Path) -> None:
    """Test files with curly braces that could break string formatting."""
    content = '# Guardrails\n\n- Use {placeholder} syntax\n- JSON: {"key": "value"}'
    guardrails_path = initialized_project / ".ralph" / "guardrails.md"
    guardrails_path.write_text(content)

    result = read_guardrails(initialized_project)
    assert "{placeholder}" in result
    assert '{"key": "value"}' in result


def test_file_with_percent_signs(initialized_project: Path) -> None:
    """Test files with percent signs that could break string formatting."""
    content = "# Handoff\n\n- Progress: 50%\n- Format: %s %d %%"
    handoff_path = initialized_project / ".ralph" / "handoff.md"
    handoff_path.write_text(content)

    result = read_handoff(initialized_project)
    assert "50%" in result
    assert "%s %d %%" in result


def test_file_with_backslashes(initialized_project: Path) -> None:
    """Test files with backslashes (Windows paths, escape sequences)."""
    content = "# Guardrails\n\n- Path: C:\\Users\\test\\file.txt\n- Escape: \\n \\t \\\\"
    guardrails_path = initialized_project / ".ralph" / "guardrails.md"
    guardrails_path.write_text(content)

    result = read_guardrails(initialized_project)
    assert "C:\\Users\\test\\file.txt" in result
    assert "\\n \\t \\\\" in result


def test_read_iteration_invalid_content(initialized_project: Path) -> None:
    """Test reading iteration with invalid (non-numeric) content."""
    iteration_path = initialized_project / ".ralph" / "iteration"
    iteration_path.write_text("not a number")

    result = read_iteration(initialized_project)
    assert result == 0  # Should return default


def test_read_done_count_invalid_content(initialized_project: Path) -> None:
    """Test reading done_count with invalid (non-numeric) content."""
    done_count_path = initialized_project / ".ralph" / "done_count"
    done_count_path.write_text("invalid")

    result = read_done_count(initialized_project)
    assert result == 0  # Should return default


def test_write_file_creates_parent_directories(temp_project: Path) -> None:
    """Test that write_file creates parent directories if needed."""
    from ralph.core.state import write_file

    nested_path = temp_project / "a" / "b" / "c" / "file.txt"
    write_file(nested_path, "content")

    assert nested_path.exists()
    assert nested_path.read_text() == "content"


def test_get_ralph_dir_with_none(temp_project: Path) -> None:
    """Test get_ralph_dir with None uses current working directory."""
    from ralph.core.state import get_ralph_dir

    result = get_ralph_dir(None)
    assert result == Path.cwd() / ".ralph"


def test_history_functions(initialized_project: Path) -> None:
    """Test history directory and file functions."""
    from ralph.core.state import get_history_dir, get_history_file, write_history

    # Test get_history_dir
    history_dir = get_history_dir(initialized_project)
    assert history_dir == initialized_project / ".ralph" / "history"

    # Test get_history_file
    history_file = get_history_file(5, initialized_project)
    assert history_file == initialized_project / ".ralph" / "history" / "005.log"

    # Test write_history
    write_history(1, "Test log content", initialized_project)
    log_file = initialized_project / ".ralph" / "history" / "001.log"
    assert log_file.exists()
    assert log_file.read_text() == "Test log content"


def test_read_prompt_md_with_none_uses_cwd(temp_project: Path) -> None:
    """Test read_prompt_md with None uses current working directory."""
    # temp_project fixture changes cwd to temp_project
    prompt_path = temp_project / "PROMPT.md"
    prompt_path.write_text("# Goal\n\nContent from CWD test")

    result = read_prompt_md(None)
    assert result is not None
    assert "Content from CWD test" in result

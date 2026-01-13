"""Tests for Claude CLI integration."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

from ralph.core.claude import (
    ClaudeError,
    ClaudeResult,
    invoke_claude,
    is_claude_available,
)

IS_WINDOWS = sys.platform == "win32"


class TestClaudeResult:
    """Tests for ClaudeResult named tuple."""

    def test_successful_result(self) -> None:
        """Test creating a successful result."""
        result = ClaudeResult(output="Hello", exit_code=0, error=None)
        assert result.output == "Hello"
        assert result.exit_code == 0
        assert result.error is None

    def test_error_result(self) -> None:
        """Test creating an error result."""
        result = ClaudeResult(output="", exit_code=1, error="Something went wrong")
        assert result.output == ""
        assert result.exit_code == 1
        assert result.error == "Something went wrong"


class TestClaudeError:
    """Tests for ClaudeError exception."""

    def test_exception_message(self) -> None:
        """Test ClaudeError can be raised with message."""
        with pytest.raises(ClaudeError) as exc_info:
            raise ClaudeError("Test error")
        assert "Test error" in str(exc_info.value)


class TestIsClaudeAvailable:
    """Tests for is_claude_available function."""

    def test_when_not_available(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test returns False when claude is not in PATH."""
        monkeypatch.setenv("PATH", "/nonexistent")
        assert is_claude_available() is False

    @pytest.mark.skipif(IS_WINDOWS, reason="Bash scripts don't work on Windows")
    def test_when_available(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test returns True when claude is in PATH."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        mock_claude = bin_dir / "claude"
        mock_claude.write_text("#!/bin/bash\necho 'mock'")
        mock_claude.chmod(mock_claude.stat().st_mode | stat.S_IEXEC)

        original_path = os.environ.get("PATH", "")
        monkeypatch.setenv("PATH", f"{bin_dir}:{original_path}")
        assert is_claude_available() is True


class TestInvokeClaude:
    """Tests for invoke_claude function."""

    @pytest.mark.skipif(IS_WINDOWS, reason="Bash scripts don't work on Windows")
    def test_with_allowed_tools(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test invoke_claude includes allowed_tools in command."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        mock_claude = bin_dir / "claude"
        # Create a mock that just echoes the arguments to verify they're passed
        mock_claude.write_text('#!/bin/bash\necho "args: $@"')
        mock_claude.chmod(mock_claude.stat().st_mode | stat.S_IEXEC)

        original_path = os.environ.get("PATH", "")
        monkeypatch.setenv("PATH", f"{bin_dir}:{original_path}")

        result = invoke_claude("test prompt", allowed_tools=["Read", "Write"])
        assert result.exit_code == 0
        assert "--allowedTools" in result.output

    @pytest.mark.skipif(IS_WINDOWS, reason="Bash scripts don't work on Windows")
    def test_timeout_handling(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test invoke_claude handles timeout."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        mock_claude = bin_dir / "claude"
        # Create a mock that sleeps longer than timeout
        mock_claude.write_text("#!/bin/bash\nsleep 10")
        mock_claude.chmod(mock_claude.stat().st_mode | stat.S_IEXEC)

        original_path = os.environ.get("PATH", "")
        monkeypatch.setenv("PATH", f"{bin_dir}:{original_path}")

        result = invoke_claude("test prompt", timeout=1)
        assert result.exit_code == -1
        assert result.error is not None
        assert "timed out" in result.error.lower()

    def test_not_found_handling(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test invoke_claude handles missing claude CLI."""
        monkeypatch.setenv("PATH", "/nonexistent")
        result = invoke_claude("test prompt")
        assert result.exit_code == -1
        assert result.error is not None
        assert "not found" in result.error.lower()

"""Tests for Agent protocol and implementations."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

from ralph.core.agent import (
    AgentResult,
    ClaudeAgent,
    CodexAgent,
    _invoke_with_streaming,
)

IS_WINDOWS = sys.platform == "win32"


class TestAgentResult:
    """Tests for AgentResult named tuple."""

    def test_successful_result(self) -> None:
        """Test creating a successful result."""
        result = AgentResult(output="Hello", exit_code=0, error=None)
        assert result.output == "Hello"
        assert result.exit_code == 0
        assert result.error is None

    def test_error_result(self) -> None:
        """Test creating an error result."""
        result = AgentResult(output="", exit_code=1, error="Something went wrong")
        assert result.output == ""
        assert result.exit_code == 1
        assert result.error == "Something went wrong"


class TestClaudeAgent:
    """Tests for ClaudeAgent implementation."""

    def test_name(self) -> None:
        """Test name property returns Claude."""
        agent = ClaudeAgent()
        assert agent.name == "Claude"

    def test_is_available_when_not_in_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test returns False when claude is not in PATH."""
        monkeypatch.setenv("PATH", "/nonexistent")
        agent = ClaudeAgent()
        assert agent.is_available() is False

    @pytest.mark.skipif(IS_WINDOWS, reason="Bash scripts don't work on Windows")
    def test_is_available_when_in_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test returns True when claude is in PATH."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        mock_claude = bin_dir / "claude"
        mock_claude.write_text("#!/bin/bash\necho 'mock'")
        mock_claude.chmod(mock_claude.stat().st_mode | stat.S_IEXEC)

        original_path = os.environ.get("PATH", "")
        monkeypatch.setenv("PATH", f"{bin_dir}:{original_path}")
        agent = ClaudeAgent()
        assert agent.is_available() is True

    @pytest.mark.skipif(IS_WINDOWS, reason="Bash scripts don't work on Windows")
    def test_invoke_timeout_handling(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test invoke handles timeout."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        mock_claude = bin_dir / "claude"
        mock_claude.write_text("#!/bin/bash\nsleep 10")
        mock_claude.chmod(mock_claude.stat().st_mode | stat.S_IEXEC)

        original_path = os.environ.get("PATH", "")
        monkeypatch.setenv("PATH", f"{bin_dir}:{original_path}")

        agent = ClaudeAgent()
        result = agent.invoke("test prompt", timeout=1)
        assert result.exit_code == -1
        assert result.error is not None
        assert "timed out" in result.error.lower()

    def test_invoke_not_found_handling(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test invoke handles missing claude CLI."""
        monkeypatch.setenv("PATH", "/nonexistent")
        agent = ClaudeAgent()
        result = agent.invoke("test prompt")
        assert result.exit_code == -1
        assert result.error is not None
        assert "not found" in result.error.lower()

    def test_is_exhausted_false_for_normal_output(self) -> None:
        """Test is_exhausted returns False for normal output."""
        agent = ClaudeAgent()
        result = AgentResult(output="Normal output", exit_code=0, error=None)
        assert agent.is_exhausted(result) is False

    def test_is_exhausted_true_for_rate_limit(self) -> None:
        """Test is_exhausted returns True for rate limit error."""
        agent = ClaudeAgent()
        result = AgentResult(output="", exit_code=1, error="Error: rate limit exceeded")
        assert agent.is_exhausted(result) is True

    def test_is_exhausted_true_for_quota_exceeded(self) -> None:
        """Test is_exhausted returns True for quota exceeded error."""
        agent = ClaudeAgent()
        result = AgentResult(output="", exit_code=1, error="quota exceeded for this month")
        assert agent.is_exhausted(result) is True

    def test_is_exhausted_true_for_token_limit(self) -> None:
        """Test is_exhausted returns True for token limit error."""
        agent = ClaudeAgent()
        result = AgentResult(output="", exit_code=1, error="token limit reached")
        assert agent.is_exhausted(result) is True

    def test_is_exhausted_true_for_usage_limit(self) -> None:
        """Test is_exhausted returns True for usage limit error."""
        agent = ClaudeAgent()
        result = AgentResult(output="", exit_code=1, error="usage limit exceeded")
        assert agent.is_exhausted(result) is True

    @pytest.mark.skipif(IS_WINDOWS, reason="Bash scripts don't work on Windows")
    def test_invoke_success(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test invoke returns output from claude CLI."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        mock_claude = bin_dir / "claude"
        mock_claude.write_text("#!/bin/bash\necho 'Hello from Claude'")
        mock_claude.chmod(mock_claude.stat().st_mode | stat.S_IEXEC)

        original_path = os.environ.get("PATH", "")
        monkeypatch.setenv("PATH", f"{bin_dir}:{original_path}")

        agent = ClaudeAgent()
        result = agent.invoke("test prompt")
        assert result.exit_code == 0
        assert "Hello from Claude" in result.output
        assert result.error is None or result.error == ""

    @pytest.mark.skipif(IS_WINDOWS, reason="Bash scripts don't work on Windows")
    def test_invoke_streams_output_to_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test invoke streams stdout and stderr to a file."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        mock_claude = bin_dir / "claude"
        mock_claude.write_text("#!/bin/bash\necho 'stdout line'\necho 'stderr line' 1>&2")
        mock_claude.chmod(mock_claude.stat().st_mode | stat.S_IEXEC)

        original_path = os.environ.get("PATH", "")
        monkeypatch.setenv("PATH", f"{bin_dir}:{original_path}")

        output_file = tmp_path / "current.log"
        agent = ClaudeAgent()
        result = agent.invoke("test prompt", output_file=output_file)

        log_content = output_file.read_text()
        assert "stdout line" in log_content
        assert "stderr line" in log_content
        assert "stdout line" in result.output
        assert "stderr line" not in result.output
        assert result.error is not None
        assert "stderr line" in result.error

    def test_is_exhausted_false_when_error_no_match(self) -> None:
        """Test is_exhausted returns False for non-matching errors."""
        agent = ClaudeAgent()
        result = AgentResult(output="", exit_code=1, error="Some random error")
        assert agent.is_exhausted(result) is False

    def test_is_exhausted_false_for_rate_limit_in_output(self) -> None:
        """Test is_exhausted returns False for rate limit in stdout."""
        agent = ClaudeAgent()
        result = AgentResult(output="Rate limit reached", exit_code=1, error=None)
        assert agent.is_exhausted(result) is False

    def test_is_exhausted_false_for_prompt_content_in_output(self) -> None:
        """Test is_exhausted ignores exhaustion keywords in stdout."""
        agent = ClaudeAgent()
        result = AgentResult(
            output="Prompt mentions usage limit and rate limit but it's fine",
            exit_code=0,
            error=None,
        )
        assert agent.is_exhausted(result) is False


class TestCodexAgent:
    """Tests for CodexAgent implementation."""

    def test_name(self) -> None:
        """Test name property returns Codex."""
        agent = CodexAgent()
        assert agent.name == "Codex"

    def test_is_available_when_not_in_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test returns False when codex is not in PATH."""
        monkeypatch.setenv("PATH", "/nonexistent")
        agent = CodexAgent()
        assert agent.is_available() is False

    @pytest.mark.skipif(IS_WINDOWS, reason="Bash scripts don't work on Windows")
    def test_is_available_when_in_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test returns True when codex is in PATH."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        mock_codex = bin_dir / "codex"
        mock_codex.write_text("#!/bin/bash\necho 'mock'")
        mock_codex.chmod(mock_codex.stat().st_mode | stat.S_IEXEC)

        original_path = os.environ.get("PATH", "")
        monkeypatch.setenv("PATH", f"{bin_dir}:{original_path}")
        agent = CodexAgent()
        assert agent.is_available() is True

    @pytest.mark.skipif(IS_WINDOWS, reason="Bash scripts don't work on Windows")
    def test_invoke_timeout_handling(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test invoke handles timeout."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        mock_codex = bin_dir / "codex"
        mock_codex.write_text("#!/bin/bash\nsleep 10")
        mock_codex.chmod(mock_codex.stat().st_mode | stat.S_IEXEC)

        original_path = os.environ.get("PATH", "")
        monkeypatch.setenv("PATH", f"{bin_dir}:{original_path}")

        agent = CodexAgent()
        result = agent.invoke("test prompt", timeout=1)
        assert result.exit_code == -1
        assert result.error is not None
        assert "timed out" in result.error.lower()

    def test_invoke_not_found_handling(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test invoke handles missing codex CLI."""
        monkeypatch.setenv("PATH", "/nonexistent")
        agent = CodexAgent()
        result = agent.invoke("test prompt")
        assert result.exit_code == -1
        assert result.error is not None
        assert "not found" in result.error.lower()

    def test_is_exhausted_false_for_normal_output(self) -> None:
        """Test is_exhausted returns False for normal output."""
        agent = CodexAgent()
        result = AgentResult(output="Normal output", exit_code=0, error=None)
        assert agent.is_exhausted(result) is False

    def test_is_exhausted_true_for_rate_limit_in_stderr(self) -> None:
        """Test is_exhausted returns True for rate_limit_exceeded in stderr."""
        agent = CodexAgent()
        result = AgentResult(output="", exit_code=1, error="rate_limit_exceeded")
        assert agent.is_exhausted(result) is True

    def test_is_exhausted_false_for_rate_limit_in_stdout(self) -> None:
        """Test is_exhausted returns False for rate_limit_exceeded in stdout."""
        agent = CodexAgent()
        result = AgentResult(output="Error: rate_limit_exceeded", exit_code=1, error=None)
        assert agent.is_exhausted(result) is False

    def test_is_exhausted_true_for_daily_limit(self) -> None:
        """Test is_exhausted returns True for daily limit error."""
        agent = CodexAgent()
        result = AgentResult(output="", exit_code=1, error="daily limit reached")
        assert agent.is_exhausted(result) is True

    def test_is_exhausted_false_for_prompt_content_in_output(self) -> None:
        """Test is_exhausted ignores exhaustion keywords in stdout."""
        agent = CodexAgent()
        result = AgentResult(
            output="Prompt says token limit and daily limit, but it's fine",
            exit_code=0,
            error=None,
        )
        assert agent.is_exhausted(result) is False

    @pytest.mark.skipif(IS_WINDOWS, reason="Bash scripts don't work on Windows")
    def test_invoke_success(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test invoke returns output from codex CLI."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        mock_codex = bin_dir / "codex"
        mock_codex.write_text("#!/bin/bash\necho 'Hello from Codex'")
        mock_codex.chmod(mock_codex.stat().st_mode | stat.S_IEXEC)

        original_path = os.environ.get("PATH", "")
        monkeypatch.setenv("PATH", f"{bin_dir}:{original_path}")

        agent = CodexAgent()
        result = agent.invoke("test prompt")
        assert result.exit_code == 0
        assert "Hello from Codex" in result.output
        assert result.error is None or result.error == ""

    @pytest.mark.skipif(IS_WINDOWS, reason="Bash scripts don't work on Windows")
    def test_invoke_streams_output_to_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test invoke streams stdout and stderr to a file."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        mock_codex = bin_dir / "codex"
        mock_codex.write_text("#!/bin/bash\necho 'codex out'\necho 'codex err' 1>&2")
        mock_codex.chmod(mock_codex.stat().st_mode | stat.S_IEXEC)

        original_path = os.environ.get("PATH", "")
        monkeypatch.setenv("PATH", f"{bin_dir}:{original_path}")

        output_file = tmp_path / "current.log"
        agent = CodexAgent()
        result = agent.invoke("test prompt", output_file=output_file)

        log_content = output_file.read_text()
        assert "codex out" in log_content
        assert "codex err" in log_content
        assert "codex out" in result.output
        assert "codex err" not in result.output
        assert result.error is not None
        assert "codex err" in result.error

    @pytest.mark.skipif(IS_WINDOWS, reason="Bash scripts don't work on Windows")
    def test_invoke_includes_required_flags(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test invoke passes required flags to codex CLI."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        mock_codex = bin_dir / "codex"
        mock_codex.write_text('#!/bin/bash\necho "$@"')
        mock_codex.chmod(mock_codex.stat().st_mode | stat.S_IEXEC)

        original_path = os.environ.get("PATH", "")
        monkeypatch.setenv("PATH", f"{bin_dir}:{original_path}")

        agent = CodexAgent()
        result = agent.invoke("test prompt")
        assert result.exit_code == 0
        assert "exec" in result.output
        assert "--dangerously-bypass-approvals-and-sandbox" in result.output

    def test_is_exhausted_false_when_error_no_match(self) -> None:
        """Test is_exhausted returns False for non-matching errors."""
        agent = CodexAgent()
        result = AgentResult(output="", exit_code=1, error="Some random error")
        assert agent.is_exhausted(result) is False

    def test_is_exhausted_false_when_output_no_match(self) -> None:
        """Test is_exhausted returns False for non-matching output."""
        agent = CodexAgent()
        result = AgentResult(output="Normal text without limit words", exit_code=0, error=None)
        assert agent.is_exhausted(result) is False


class TestRealTimeStderrMonitoring:
    """Tests for real-time stderr monitoring and crash pattern detection."""

    @pytest.mark.skipif(IS_WINDOWS, reason="Bash scripts don't work on Windows")
    def test_crash_pattern_in_stderr_kills_process(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that a crash pattern in stderr kills the hung process."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        mock_script = bin_dir / "hung_script"
        # Script writes crash pattern to stderr, then hangs forever
        mock_script.write_text(
            "#!/bin/bash\n"
            "echo 'starting' >&2\n"
            "echo 'ECONNRESET: connection reset' >&2\n"
            "sleep 100\n"  # Hang forever
        )
        mock_script.chmod(mock_script.stat().st_mode | stat.S_IEXEC)

        output_file = tmp_path / "output.log"
        result = _invoke_with_streaming(
            [str(mock_script)],
            timeout=10,
            output_file=output_file,
            crash_patterns=[r"econnreset"],
        )

        # Process should have been killed (SIGKILL = -9 on Linux)
        assert result.exit_code < 0  # Killed by signal
        assert "ECONNRESET" in (result.error or "")

    @pytest.mark.skipif(IS_WINDOWS, reason="Bash scripts don't work on Windows")
    def test_crash_pattern_etimedout_kills_process(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that ETIMEDOUT pattern in stderr kills the process."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        mock_script = bin_dir / "hung_script"
        mock_script.write_text("#!/bin/bash\necho 'Connection error: ETIMEDOUT' >&2\nsleep 100\n")
        mock_script.chmod(mock_script.stat().st_mode | stat.S_IEXEC)

        output_file = tmp_path / "output.log"
        result = _invoke_with_streaming(
            [str(mock_script)],
            timeout=10,
            output_file=output_file,
            crash_patterns=[r"etimedout"],
        )

        assert result.exit_code < 0  # Killed by signal
        assert "ETIMEDOUT" in (result.error or "")

    @pytest.mark.skipif(IS_WINDOWS, reason="Bash scripts don't work on Windows")
    def test_no_messages_pattern_kills_process(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that 'No messages returned' pattern kills the process."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        mock_script = bin_dir / "hung_script"
        mock_script.write_text(
            "#!/bin/bash\necho 'Error: No messages returned from API' >&2\nsleep 100\n"
        )
        mock_script.chmod(mock_script.stat().st_mode | stat.S_IEXEC)

        output_file = tmp_path / "output.log"
        result = _invoke_with_streaming(
            [str(mock_script)],
            timeout=10,
            output_file=output_file,
            crash_patterns=[r"no messages returned"],
        )

        assert result.exit_code < 0  # Killed by signal
        assert "No messages returned" in (result.error or "")

    @pytest.mark.skipif(IS_WINDOWS, reason="Bash scripts don't work on Windows")
    def test_no_crash_patterns_does_not_affect_normal_run(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that without crash patterns, process runs normally."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        mock_script = bin_dir / "normal_script"
        mock_script.write_text("#!/bin/bash\necho 'stdout output'\necho 'stderr output' >&2\n")
        mock_script.chmod(mock_script.stat().st_mode | stat.S_IEXEC)

        output_file = tmp_path / "output.log"
        result = _invoke_with_streaming(
            [str(mock_script)],
            timeout=10,
            output_file=output_file,
            crash_patterns=None,
        )

        assert result.exit_code == 0
        assert "stdout output" in result.output
        assert "stderr output" in (result.error or "")

    @pytest.mark.skipif(IS_WINDOWS, reason="Bash scripts don't work on Windows")
    def test_non_matching_stderr_does_not_kill_process(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that non-matching stderr content doesn't trigger crash detection."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        mock_script = bin_dir / "warning_script"
        mock_script.write_text(
            "#!/bin/bash\necho 'Some warning: connection slow' >&2\necho 'done'\n"
        )
        mock_script.chmod(mock_script.stat().st_mode | stat.S_IEXEC)

        output_file = tmp_path / "output.log"
        result = _invoke_with_streaming(
            [str(mock_script)],
            timeout=10,
            output_file=output_file,
            crash_patterns=[r"econnreset", r"etimedout"],
        )

        assert result.exit_code == 0
        assert "done" in result.output

    @pytest.mark.skipif(IS_WINDOWS, reason="Bash scripts don't work on Windows")
    def test_crash_pattern_via_agent_invoke(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that crash patterns work through Agent.invoke."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        mock_claude = bin_dir / "claude"
        mock_claude.write_text(
            "#!/bin/bash\n"
            "echo 'starting' >&2\n"
            "echo 'ECONNRESET: connection reset by peer' >&2\n"
            "sleep 100\n"
        )
        mock_claude.chmod(mock_claude.stat().st_mode | stat.S_IEXEC)

        original_path = os.environ.get("PATH", "")
        monkeypatch.setenv("PATH", f"{bin_dir}:{original_path}")

        output_file = tmp_path / "output.log"
        agent = ClaudeAgent()
        result = agent.invoke(
            "test",
            timeout=10,
            output_file=output_file,
            crash_patterns=[r"econnreset"],
        )

        assert result.exit_code < 0  # Killed by signal
        assert "ECONNRESET" in (result.error or "")

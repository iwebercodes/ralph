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

    def test_is_exhausted_false_for_exit_code_zero(self) -> None:
        """Test is_exhausted returns False when exit code is 0, regardless of stderr."""
        agent = CodexAgent()
        # Even if stderr mentions usage limits, exit code 0 means success
        result = AgentResult(
            output="Success",
            exit_code=0,
            error="Discussing token limits and usage_limit_reached in context",
        )
        assert agent.is_exhausted(result) is False

    def test_is_exhausted_false_for_broad_patterns(self) -> None:
        """Test is_exhausted ignores broad patterns that caused false positives."""
        agent = CodexAgent()
        # These broad patterns used to trigger false positives
        broad_error_messages = [
            "rate limit discussion in the context",
            "token limit explained in documentation",
            "usage limit is configurable",
            "daily limit for API calls",
            "rate_limit_exceeded in the log",
        ]
        for error in broad_error_messages:
            result = AgentResult(output="", exit_code=1, error=error)
            assert agent.is_exhausted(result) is False, f"False positive for: {error}"

    def test_is_exhausted_true_for_usage_limit_reached(self) -> None:
        """Test is_exhausted detects usage_limit_reached API error type."""
        agent = CodexAgent()
        result = AgentResult(
            output="",
            exit_code=1,
            error='error=http 429: {"error":{"type":"usage_limit_reached"}}',
        )
        assert agent.is_exhausted(result) is True

    def test_is_exhausted_true_for_429_status(self) -> None:
        """Test is_exhausted detects 429 Too Many Requests HTTP status."""
        agent = CodexAgent()
        result = AgentResult(
            output="",
            exit_code=1,
            error="error=http 429 Too Many Requests: ...",
        )
        assert agent.is_exhausted(result) is True

    def test_is_exhausted_true_for_hit_usage_limit_message(self) -> None:
        """Test is_exhausted detects 'You've hit your usage limit' message."""
        agent = CodexAgent()
        result = AgentResult(
            output="",
            exit_code=1,
            error="ERROR: You've hit your usage limit. Upgrade to Pro...",
        )
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

    def test_exhaustion_reason_returns_none_for_exit_code_zero(self) -> None:
        """Test exhaustion_reason returns None when exit code is 0."""
        agent = CodexAgent()
        result = AgentResult(
            output="",
            exit_code=0,
            error="usage_limit_reached",
        )
        assert agent.exhaustion_reason(result) is None

    def test_exhaustion_reason_includes_reset_time(self) -> None:
        """Test exhaustion_reason extracts and formats reset time from JSON error."""
        agent = CodexAgent()
        result = AgentResult(
            output="",
            exit_code=1,
            error='{"error":{"type":"usage_limit_reached","resets_in_seconds":2021}}',
        )
        reason = agent.exhaustion_reason(result)
        assert reason is not None
        assert "usage limit reached" in reason
        assert "33 minutes" in reason  # 2021 seconds ≈ 33 minutes

    def test_exhaustion_reason_without_reset_time(self) -> None:
        """Test exhaustion_reason works without reset time."""
        agent = CodexAgent()
        result = AgentResult(
            output="",
            exit_code=1,
            error="You've hit your usage limit. Upgrade to Pro.",
        )
        reason = agent.exhaustion_reason(result)
        assert reason == "usage limit reached"


class TestCodexExhaustionRealStderr:
    """Integration tests with real Codex stderr samples."""

    # Real stderr output from Codex when hitting usage limit
    REAL_EXHAUSTION_STDERR = """OpenAI Codex v0.88.0 (research preview)
--------
workdir: /path/to/project
model: gpt-5.2-codex
provider: openai
approval: never
sandbox: danger-full-access
reasoning effort: none
reasoning summaries: auto
session id: abc-123-def
--------
user
Say hello
mcp startup: no servers
2026-01-29T23:21:37.939876Z ERROR codex_api::endpoint::responses: error=http 429 Too Many Requests: Some("{\\"error\\":{\\"type\\":\\"usage_limit_reached\\",\\"message\\":\\"The usage limit has been reached\\",\\"plan_type\\":\\"plus\\",\\"resets_at\\":1769730918,\\"resets_in_seconds\\":2021}}")
ERROR: You've hit your usage limit. Upgrade to Pro (https://openai.com/chatgpt/pricing), visit https://chatgpt.com/codex/settings/usage to purchase more credits or try again at 12:55 AM."""

    # Normal operational stderr from Codex
    NORMAL_OPERATIONAL_STDERR = """OpenAI Codex v0.88.0 (research preview)
--------
workdir: /path/to/project
model: gpt-5.2-codex
provider: openai
approval: never
sandbox: danger-full-access
reasoning effort: none
reasoning summaries: auto
session id: xyz-789-uvw
--------
user
Please implement a function that checks token limits and handles usage limits gracefully
mcp startup: no servers
thinking...
The function should consider the context window token limit when processing input."""

    def test_real_exhaustion_stderr_detected(self) -> None:
        """Test that real exhaustion stderr triggers detection with exit code 1."""
        agent = CodexAgent()
        result = AgentResult(
            output="",
            exit_code=1,
            error=self.REAL_EXHAUSTION_STDERR,
        )
        assert agent.is_exhausted(result) is True

    def test_real_exhaustion_stderr_extracts_reset_time(self) -> None:
        """Test that reset time is extracted from real exhaustion stderr."""
        agent = CodexAgent()
        result = AgentResult(
            output="",
            exit_code=1,
            error=self.REAL_EXHAUSTION_STDERR,
        )
        reason = agent.exhaustion_reason(result)
        assert reason is not None
        assert "33 minutes" in reason  # 2021 seconds ≈ 33 minutes

    def test_normal_operational_stderr_not_detected_with_exit_0(self) -> None:
        """Test that normal operational stderr with exit 0 is not detected."""
        agent = CodexAgent()
        result = AgentResult(
            output="Function implemented successfully",
            exit_code=0,
            error=self.NORMAL_OPERATIONAL_STDERR,
        )
        assert agent.is_exhausted(result) is False

    def test_normal_operational_stderr_not_detected_with_exit_1(self) -> None:
        """Test that normal operational stderr without specific patterns is not detected."""
        agent = CodexAgent()
        # Even with exit code 1, the normal operational stderr shouldn't trigger
        # because it doesn't contain the specific exhaustion patterns
        result = AgentResult(
            output="",
            exit_code=1,
            error=self.NORMAL_OPERATIONAL_STDERR,
        )
        assert agent.is_exhausted(result) is False

    def test_all_three_patterns_detected(self) -> None:
        """Test that each specific pattern correctly identifies exhaustion."""
        agent = CodexAgent()

        # Pattern 1: usage_limit_reached (API error type)
        result1 = AgentResult(
            output="",
            exit_code=1,
            error='{"error":{"type":"usage_limit_reached"}}',
        )
        assert agent.is_exhausted(result1) is True

        # Pattern 2: 429 Too Many Requests (HTTP status)
        result2 = AgentResult(
            output="",
            exit_code=1,
            error="error=http 429 Too Many Requests: ...",
        )
        assert agent.is_exhausted(result2) is True

        # Pattern 3: You've hit your usage limit (error message)
        result3 = AgentResult(
            output="",
            exit_code=1,
            error="ERROR: You've hit your usage limit. Upgrade to Pro",
        )
        assert agent.is_exhausted(result3) is True


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

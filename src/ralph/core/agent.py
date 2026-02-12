"""Agent protocol and implementations for invoking AI assistants."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple, Protocol, TextIO


class AgentResult(NamedTuple):
    """Result of an agent invocation."""

    output: str
    exit_code: int
    error: str | None


class Agent(Protocol):
    """Protocol for AI agents that can execute prompts."""

    @property
    def name(self) -> str:
        """Human-readable name for this agent."""
        ...

    def is_available(self) -> bool:
        """Check if this agent's CLI is available."""
        ...

    def invoke(
        self,
        prompt: str,
        timeout: int | None = 10800,
        output_file: Path | None = None,
        crash_patterns: list[str] | None = None,
    ) -> AgentResult:
        """Invoke the agent with a prompt.

        Args:
            prompt: The prompt to send to the agent
            timeout: Timeout in seconds (default 3 hours), None for no timeout
            output_file: Optional file to stream output to in real time
            crash_patterns: Deprecated. Kept for backward-compatible call sites.

        Returns:
            AgentResult with output, exit code, and any error message
        """
        ...

    def is_exhausted(self, result: AgentResult) -> bool:
        """Check if the agent is exhausted (rate limited, quota exceeded).

        Args:
            result: The result from the most recent invocation

        Returns:
            True if the agent should be removed from the pool
        """
        ...

    def exhaustion_reason(self, result: AgentResult) -> str | None:
        """Return the matched exhaustion reason, if any."""
        ...


class ClaudeAgent:
    """Agent implementation using Claude CLI."""

    @property
    def name(self) -> str:
        return "Claude"

    def is_available(self) -> bool:
        """Check if claude CLI is available in PATH."""
        return shutil.which("claude") is not None

    def invoke(
        self,
        prompt: str,
        timeout: int | None = 10800,
        output_file: Path | None = None,
        crash_patterns: list[str] | None = None,
    ) -> AgentResult:
        """Invoke Claude CLI with the given prompt."""
        claude_path = shutil.which("claude")
        if claude_path is None:
            return AgentResult(
                output="",
                exit_code=-1,
                error="claude CLI not found in PATH",
            )

        cmd = [
            claude_path,
            "-p",
            prompt,
            "--output-format",
            "text",
            "--dangerously-skip-permissions",
        ]

        return _invoke_command(
            cmd,
            timeout=timeout,
            output_file=output_file,
            timeout_message="Claude invocation timed out",
            not_found_message="claude CLI not found in PATH",
            crash_patterns=crash_patterns,
        )

    def is_exhausted(self, result: AgentResult) -> bool:
        """Check if Claude is exhausted based on stdout signature output."""
        if result.exit_code == 0:
            return False
        return _claude_extract_exhaustion_info(result.output) is not None

    def exhaustion_reason(self, result: AgentResult) -> str | None:
        """Return a human-readable Claude exhaustion reason with reset time if available."""
        if result.exit_code == 0:
            return None
        info = _claude_extract_exhaustion_info(result.output)
        if info is None:
            return None
        _, reset_epoch = info
        if reset_epoch is None:
            return "usage limit reached"
        reset_at = datetime.fromtimestamp(reset_epoch, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M UTC"
        )
        return f"usage limit reached (resets at {reset_at})"


class CodexAgent:
    """Agent implementation using OpenAI Codex CLI."""

    # Specific patterns that only match actual exhaustion errors.
    # These are designed to avoid false positives from informational stderr output.
    _EXHAUSTION_PATTERNS = [
        r"usage_limit_reached",  # API error type from JSON response
        r"429 Too Many Requests",  # HTTP status code
        r"You've hit your usage limit",  # Unambiguous error message
    ]

    @property
    def name(self) -> str:
        return "Codex"

    def is_available(self) -> bool:
        """Check if codex CLI is available in PATH."""
        return shutil.which("codex") is not None

    def invoke(
        self,
        prompt: str,
        timeout: int | None = 10800,
        output_file: Path | None = None,
        crash_patterns: list[str] | None = None,
    ) -> AgentResult:
        """Invoke Codex CLI with the given prompt."""
        codex_path = shutil.which("codex")
        if codex_path is None:
            return AgentResult(
                output="",
                exit_code=-1,
                error="codex CLI not found in PATH",
            )

        cmd = [
            codex_path,
            "exec",
            "-C",
            os.getcwd(),
            "--skip-git-repo-check",
            "--dangerously-bypass-approvals-and-sandbox",
            prompt,
        ]

        return _invoke_command(
            cmd,
            timeout=timeout,
            output_file=output_file,
            timeout_message="Codex invocation timed out",
            not_found_message="codex CLI not found in PATH",
            crash_patterns=crash_patterns,
        )

    def is_exhausted(self, result: AgentResult) -> bool:
        """Check if Codex is exhausted based on error output.

        Only returns True if:
        1. The exit code indicates failure (non-zero)
        2. The stderr contains a specific exhaustion pattern
        """
        if result.exit_code == 0:
            return False
        return _codex_extract_exhaustion_info(result.error) is not None

    def exhaustion_reason(self, result: AgentResult) -> str | None:
        """Return a human-readable exhaustion reason with reset time if available."""
        if result.exit_code == 0:
            return None
        info = _codex_extract_exhaustion_info(result.error)
        if info is None:
            return None
        pattern, reset_seconds = info
        if reset_seconds is not None:
            return f"{pattern} (resets in {_format_duration(reset_seconds)})"
        return pattern


def _extract_exhaustion_reason(patterns: list[str], error: str | None) -> str | None:
    if not error:
        return None
    error_lower = error.lower()
    for pattern in patterns:
        match = re.search(pattern, error_lower)
        if match:
            reason = match.group(0)
            reason = re.sub(r"[_\W]+", " ", reason)
            reason = re.sub(r"\s+", " ", reason).strip()
            return reason
    return None


def _codex_extract_exhaustion_info(error: str | None) -> tuple[str, int | None] | None:
    """Extract exhaustion pattern and reset time from Codex error output.

    Returns:
        A tuple of (pattern_matched, reset_seconds) if exhaustion detected,
        where reset_seconds may be None if not available. Returns None if
        no exhaustion pattern matched.
    """
    if not error:
        return None

    runtime_error = _codex_runtime_error_text(error)
    if runtime_error is None:
        return None

    # Check for specific exhaustion patterns
    patterns = [
        (r"usage_limit_reached", "usage limit reached"),
        (r"429 Too Many Requests", "429 Too Many Requests"),
        (r"You've hit your usage limit", "usage limit reached"),
    ]

    matched_reason = None
    for pattern, reason in patterns:
        if re.search(pattern, runtime_error):
            matched_reason = reason
            break

    if matched_reason is None:
        return None

    # Try to extract reset time from JSON error (handles both escaped and unescaped quotes)
    reset_seconds = None
    reset_match = re.search(
        r'(?:\\"|")?resets_in_seconds(?:\\"|")?\s*:\s*(\d+)',
        runtime_error,
    )
    if reset_match:
        reset_seconds = int(reset_match.group(1))

    return (matched_reason, reset_seconds)


def _codex_runtime_error_text(error: str) -> str | None:
    """Return the runtime/error section of Codex stderr.

    Codex echoes the user prompt to stderr before runtime errors. To avoid
    false positives from prompt text, exhaustion matching starts from the first
    runtime error anchor.
    """
    search_start = 0
    user_block = re.search(r"^user\s*$", error, re.MULTILINE)
    if user_block:
        mcp_start = re.search(r"^mcp startup:.*$", error[user_block.end() :], re.MULTILINE)
        if mcp_start:
            mcp_line_start = user_block.end() + mcp_start.start()
            mcp_line_end = error.find("\n", mcp_line_start)
            search_start = len(error) if mcp_line_end == -1 else mcp_line_end + 1

    anchor_patterns = [
        r"codex_api::endpoint::responses",
        r"^\d{4}-\d{2}-\d{2}T[^\n]*\bERROR\b",
        r"^ERROR:",
    ]
    start_index: int | None = None
    search_text = error[search_start:]
    for pattern in anchor_patterns:
        match = re.search(pattern, search_text, re.MULTILINE)
        if match:
            absolute_index = search_start + match.start()
            if start_index is None or absolute_index < start_index:
                start_index = absolute_index
    if start_index is None:
        return None
    return error[start_index:]


def _claude_extract_exhaustion_info(output: str | None) -> tuple[str, int | None] | None:
    """Extract exhaustion signature and reset epoch from Claude stdout output."""
    if not output:
        return None

    match = re.search(r"^\s*Claude AI usage limit reached\|(\d+)\s*$", output, re.MULTILINE)
    if not match:
        return None

    reset_epoch = int(match.group(1))
    return ("usage limit reached", reset_epoch)


def _format_duration(seconds: int) -> str:
    """Format a duration in seconds as a human-readable string."""
    if seconds < 60:
        return f"{seconds} seconds"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} minutes" if minutes > 1 else "1 minute"
    hours = minutes // 60
    remaining_minutes = minutes % 60
    if remaining_minutes == 0:
        return f"{hours} hours" if hours > 1 else "1 hour"
    return (
        f"{hours} hours {remaining_minutes} minutes"
        if hours > 1
        else f"1 hour {remaining_minutes} minutes"
    )


def _invoke_command(
    cmd: list[str],
    timeout: int | None,
    output_file: Path | None,
    timeout_message: str,
    not_found_message: str,
    crash_patterns: list[str] | None = None,
) -> AgentResult:
    """Invoke a command with optional streaming to a file."""
    try:
        if output_file is None:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return AgentResult(
                output=result.stdout,
                exit_code=result.returncode,
                error=result.stderr or None,
            )

        return _invoke_with_streaming(cmd, timeout, output_file)
    except subprocess.TimeoutExpired:
        return AgentResult(
            output="",
            exit_code=-1,
            error=timeout_message,
        )
    except FileNotFoundError:
        return AgentResult(
            output="",
            exit_code=-1,
            error=not_found_message,
        )


def _invoke_with_streaming(
    cmd: list[str],
    timeout: int | None,
    output_file: Path,
) -> AgentResult:
    """Invoke a command while streaming output line-by-line to a file."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    lock = threading.Lock()

    def _read_stdout(stream: TextIO) -> None:
        while True:
            line = stream.readline()
            if line == "":
                break
            stdout_lines.append(line)
            with lock:
                log_file.write(line)
                log_file.flush()

    def _read_stderr(stream: TextIO) -> None:
        while True:
            line = stream.readline()
            if line == "":
                break
            stderr_lines.append(line)
            with lock:
                log_file.write(line)
                log_file.flush()

    with output_file.open("a", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        if process.stdout is None or process.stderr is None:
            raise RuntimeError("Failed to capture subprocess output")

        stdout_thread = threading.Thread(target=_read_stdout, args=(process.stdout,))
        stderr_thread = threading.Thread(target=_read_stderr, args=(process.stderr,))
        stdout_thread.daemon = True
        stderr_thread.daemon = True
        stdout_thread.start()
        stderr_thread.start()

        try:
            # Poll for process completion
            elapsed = 0.0
            poll_interval = 0.1
            while True:
                try:
                    process.wait(timeout=poll_interval)
                    break  # Process finished normally
                except subprocess.TimeoutExpired:
                    elapsed += poll_interval
                    if timeout is not None and elapsed >= timeout:
                        process.kill()
                        process.wait()
                        raise subprocess.TimeoutExpired(cmd, timeout) from None
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise
        finally:
            stdout_thread.join(timeout=1.0)
            stderr_thread.join(timeout=1.0)

    output = "".join(stdout_lines)
    error = "".join(stderr_lines)

    return AgentResult(
        output=output,
        exit_code=process.returncode or 0,
        error=error or None,
    )

"""Agent protocol and implementations for invoking AI assistants."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
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
            crash_patterns: Regex patterns to monitor in stderr. If a pattern
                matches, the process is killed immediately.

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


class ClaudeAgent:
    """Agent implementation using Claude CLI."""

    _EXHAUSTION_PATTERNS = [
        r"rate.?limit",
        r"quota.?exceeded",
        r"token.?limit",
        r"usage.?limit",
        r"rate_limit_exceeded",
        r"daily.?limit",
    ]

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
        """Check if Claude is exhausted based on error output."""
        if not result.error:
            return False
        error_lower = result.error.lower()
        return any(re.search(pattern, error_lower) for pattern in self._EXHAUSTION_PATTERNS)


class CodexAgent:
    """Agent implementation using OpenAI Codex CLI."""

    _EXHAUSTION_PATTERNS = [
        r"rate.?limit",
        r"quota.?exceeded",
        r"token.?limit",
        r"usage.?limit",
        r"rate_limit_exceeded",
        r"daily.?limit",
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
        """Check if Codex is exhausted based on error output."""
        if not result.error:
            return False
        error_lower = result.error.lower()
        return any(re.search(pattern, error_lower) for pattern in self._EXHAUSTION_PATTERNS)


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

        return _invoke_with_streaming(cmd, timeout, output_file, crash_patterns)
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
    crash_patterns: list[str] | None = None,
) -> AgentResult:
    """Invoke a command while streaming output line-by-line to a file.

    If crash_patterns is provided, stderr is monitored in real-time. When a
    crash pattern is detected, the process is killed immediately.
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    lock = threading.Lock()
    crash_detected = threading.Event()

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
            if crash_patterns:
                for pattern in crash_patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        crash_detected.set()
                        return

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
            # Poll for process completion or crash detection
            elapsed = 0.0
            poll_interval = 0.1
            while True:
                if crash_detected.is_set():
                    process.kill()
                    process.wait()
                    break
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

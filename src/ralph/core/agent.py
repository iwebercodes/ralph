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
    ) -> AgentResult:
        """Invoke the agent with a prompt.

        Args:
            prompt: The prompt to send to the agent
            timeout: Timeout in seconds (default 3 hours), None for no timeout
            output_file: Optional file to stream output to in real time

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

    def _read_stream(stream: TextIO, buffer: list[str]) -> None:
        while True:
            line = stream.readline()
            if line == "":
                break
            buffer.append(line)
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

        threads = [
            threading.Thread(target=_read_stream, args=(process.stdout, stdout_lines)),
            threading.Thread(target=_read_stream, args=(process.stderr, stderr_lines)),
        ]
        for thread in threads:
            thread.daemon = True
            thread.start()

        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise
        finally:
            for thread in threads:
                thread.join()

    output = "".join(stdout_lines)
    error = "".join(stderr_lines)
    return AgentResult(
        output=output,
        exit_code=process.returncode or 0,
        error=error or None,
    )

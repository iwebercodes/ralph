"""Agent protocol and implementations for invoking AI assistants."""

from __future__ import annotations

import re
import shutil
import subprocess
from typing import NamedTuple, Protocol


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

    def invoke(self, prompt: str, timeout: int = 1800) -> AgentResult:
        """Invoke the agent with a prompt.

        Args:
            prompt: The prompt to send to the agent
            timeout: Timeout in seconds (default 30 minutes)

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

    def invoke(self, prompt: str, timeout: int = 1800) -> AgentResult:
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

        try:
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
        except subprocess.TimeoutExpired:
            return AgentResult(
                output="",
                exit_code=-1,
                error="Claude invocation timed out",
            )
        except FileNotFoundError:
            return AgentResult(
                output="",
                exit_code=-1,
                error="claude CLI not found in PATH",
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

    def invoke(self, prompt: str, timeout: int = 1800) -> AgentResult:
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
            "--dangerously-bypass-approvals-and-sandbox",
            prompt,
        ]

        try:
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
        except subprocess.TimeoutExpired:
            return AgentResult(
                output="",
                exit_code=-1,
                error="Codex invocation timed out",
            )
        except FileNotFoundError:
            return AgentResult(
                output="",
                exit_code=-1,
                error="codex CLI not found in PATH",
            )

    def is_exhausted(self, result: AgentResult) -> bool:
        """Check if Codex is exhausted based on error output."""
        if not result.error:
            return False
        error_lower = result.error.lower()
        return any(re.search(pattern, error_lower) for pattern in self._EXHAUSTION_PATTERNS)

"""Claude CLI integration."""

from __future__ import annotations

import shutil
import subprocess
from typing import NamedTuple


class ClaudeResult(NamedTuple):
    """Result of a Claude invocation."""

    output: str
    exit_code: int
    error: str | None


class ClaudeError(Exception):
    """Error from Claude CLI."""

    pass


def is_claude_available() -> bool:
    """Check if claude CLI is available in PATH."""
    return shutil.which("claude") is not None


def invoke_claude(
    prompt: str,
    allowed_tools: list[str] | None = None,
    timeout: int = 1800,
) -> ClaudeResult:
    """Invoke Claude CLI with the given prompt.

    Args:
        prompt: The prompt to send to Claude
        allowed_tools: Optional list of tools to allow
        timeout: Timeout in seconds (default 30 minutes)

    Returns:
        ClaudeResult with output, exit code, and any error message
    """
    # Use shutil.which to get full path, needed for Windows to find .cmd files
    claude_path = shutil.which("claude")
    if claude_path is None:
        return ClaudeResult(
            output="",
            exit_code=-1,
            error="claude CLI not found in PATH",
        )

    cmd = [claude_path, "-p", prompt, "--output-format", "text", "--dangerously-skip-permissions"]

    if allowed_tools:
        for tool in allowed_tools:
            cmd.extend(["--allowedTools", tool])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return ClaudeResult(
            output=result.stdout,
            exit_code=result.returncode,
            error=result.stderr if result.returncode != 0 else None,
        )
    except subprocess.TimeoutExpired:
        return ClaudeResult(
            output="",
            exit_code=-1,
            error="Claude invocation timed out",
        )
    except FileNotFoundError:
        return ClaudeResult(
            output="",
            exit_code=-1,
            error="claude CLI not found in PATH",
        )

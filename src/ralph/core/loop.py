"""Main loop engine for Ralph."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

from ralph.core.agent import Agent, AgentResult
from ralph.core.ignore import create_spec, load_ignore_patterns
from ralph.core.pool import AgentPool
from ralph.core.prompt import assemble_prompt
from ralph.core.snapshot import compare_snapshots, take_snapshot
from ralph.core.state import (
    Status,
    read_done_count,
    read_guardrails,
    read_handoff,
    read_iteration,
    read_prompt_md,
    read_status,
    write_done_count,
    write_history,
    write_iteration,
    write_status,
)


class IterationResult(NamedTuple):
    """Result of a single iteration."""

    status: Status
    files_changed: list[str]
    test_result: tuple[int, str] | None  # (exit_code, output) or None
    claude_output: str  # Kept for backward compatibility
    agent_result: AgentResult | None = None  # Full result for exhaustion checking


class LoopResult(NamedTuple):
    """Result of running the loop."""

    exit_code: int
    message: str
    iterations_run: int


def run_test_command(cmd: str) -> tuple[int, str]:
    """Run a test command and return (exit_code, output)."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout for tests
        )
        output = result.stdout + result.stderr
        return (result.returncode, output)
    except subprocess.TimeoutExpired:
        return (-1, "Test command timed out")
    except Exception as e:
        return (-1, f"Test command failed: {e}")


def format_log_entry(
    iteration: int,
    prompt: str,
    agent_output: str,
    agent_name: str,
    status: Status,
    files_changed: list[str],
    test_result: tuple[int, str] | None,
) -> str:
    """Format a log entry for history."""
    timestamp = datetime.now(timezone.utc).isoformat()
    lines = [
        "=" * 80,
        f"RALPH ROTATION {iteration} [{agent_name}] - {timestamp}",
        "=" * 80,
        "",
        "--- PROMPT SENT ---",
        prompt,
        "",
        "--- AGENT OUTPUT ---",
        agent_output,
        "",
        "--- STATUS ---",
        f"Signal: {status.value}",
        f"Files Changed: {len(files_changed)}",
    ]

    if files_changed:
        for f in files_changed:
            lines.append(f"  - {f}")

    if test_result:
        exit_code, output = test_result
        lines.extend(
            [
                "",
                "--- TEST COMMAND ---",
                f"Exit Code: {exit_code}",
                "Output:",
                output,
            ]
        )

    lines.append("")
    lines.append("=" * 80)
    return "\n".join(lines)


def run_iteration(
    iteration: int,
    max_iter: int,
    test_cmd: str | None,
    agent: Agent,
    root: Path | None = None,
) -> IterationResult:
    """Run a single iteration of the loop.

    Args:
        iteration: Current iteration number
        max_iter: Maximum number of iterations
        test_cmd: Optional test command to run after the iteration
        agent: The agent to use for this iteration
        root: Project root directory
    """
    if root is None:
        root = Path.cwd()

    # Load ignore patterns and create spec
    patterns = load_ignore_patterns(root)
    spec = create_spec(patterns)

    # Take pre-iteration snapshot
    snapshot_before = take_snapshot(root, spec)

    # Read state
    done_count = read_done_count(root)
    goal = read_prompt_md(root) or ""
    handoff = read_handoff(root)
    guardrails = read_guardrails(root)

    # Assemble prompt
    prompt = assemble_prompt(
        iteration=iteration,
        max_iter=max_iter,
        done_count=done_count,
        goal=goal,
        handoff=handoff,
        guardrails=guardrails,
    )

    # Reset status to IDLE before invoking agent.
    # This ensures each iteration starts with a known state - if the agent doesn't
    # write a new status, we get IDLE instead of stale data from previous iteration.
    write_status(Status.IDLE, root)

    # Invoke agent
    result: AgentResult = agent.invoke(prompt)

    # Parse status
    status = read_status(root)

    # Run test command if specified
    test_result = None
    if test_cmd:
        test_result = run_test_command(test_cmd)

    # Take post-iteration snapshot
    snapshot_after = take_snapshot(root, spec)

    # Detect changes
    files_changed = compare_snapshots(snapshot_before, snapshot_after)

    # Write history log
    log_content = format_log_entry(
        iteration=iteration,
        prompt=prompt,
        agent_output=result.output,
        agent_name=agent.name,
        status=status,
        files_changed=files_changed,
        test_result=test_result,
    )
    write_history(iteration, log_content, root)

    return IterationResult(
        status=status,
        files_changed=files_changed,
        test_result=test_result,
        claude_output=result.output,
        agent_result=result,
    )


def handle_status(
    status: Status,
    files_changed: list[str],
    done_count: int,
    root: Path | None = None,
) -> tuple[str, int | None, int]:
    """Handle status signal and return (action, exit_code or None, new_done_count).

    action: "continue", "exit"
    exit_code: None if continuing, otherwise the exit code
    """
    if status == Status.STUCK:
        return ("exit", 2, done_count)

    if status == Status.DONE:
        if files_changed:
            # Changes made during DONE - reset verification
            write_done_count(0, root)
            return ("continue", None, 0)

        # No changes - increment verification counter
        done_count += 1
        write_done_count(done_count, root)

        if done_count >= 3:
            return ("exit", 0, done_count)

        return ("continue", None, done_count)

    # CONTINUE or ROTATE - reset done_count and continue
    if done_count > 0:
        write_done_count(0, root)
    return ("continue", None, 0)


def run_loop(
    max_iter: int = 20,
    test_cmd: str | None = None,
    root: Path | None = None,
    agent_pool: AgentPool | None = None,
    on_iteration_start: Callable[[int, int, int, str], None] | None = None,
    on_iteration_end: Callable[[int, IterationResult, int, str], None] | None = None,
) -> LoopResult:
    """Run the main Ralph loop.

    Args:
        max_iter: Maximum number of iterations
        test_cmd: Optional test command to run after each iteration
        root: Project root directory
        agent_pool: Pool of agents to use (required)
        on_iteration_start: Callback(iteration, max_iter, done_count, agent_name)
        on_iteration_end: Callback(iteration, result, done_count, agent_name)

    Returns:
        LoopResult with exit code, message, and iterations run
    """
    if root is None:
        root = Path.cwd()

    if agent_pool is None:
        raise ValueError("agent_pool is required")

    iteration = read_iteration(root)
    done_count = read_done_count(root)
    iterations_run = 0

    while iteration < max_iter:
        # Check if we have any agents left
        if agent_pool.is_empty():
            return LoopResult(4, "All agents exhausted", iterations_run)

        # Select an agent for this iteration
        agent = agent_pool.select_random()

        iteration += 1
        write_iteration(iteration, root)
        iterations_run += 1

        if on_iteration_start:
            on_iteration_start(iteration, max_iter, done_count, agent.name)

        result = run_iteration(iteration, max_iter, test_cmd, agent, root)

        # Check if agent is exhausted
        if result.agent_result and agent.is_exhausted(result.agent_result):
            agent_pool.remove(agent)
            # If this was our last agent, exit
            if agent_pool.is_empty():
                return LoopResult(4, "All agents exhausted", iterations_run)

        action, exit_code, done_count = handle_status(
            result.status,
            result.files_changed,
            done_count,
            root,
        )

        if on_iteration_end:
            on_iteration_end(iteration, result, done_count, agent.name)

        if action == "exit":
            if exit_code == 0:
                return LoopResult(0, "Goal achieved!", iterations_run)
            elif exit_code == 2:
                return LoopResult(2, "Ralph needs help. Check .ralph/handoff.md", iterations_run)
            else:
                return LoopResult(exit_code or 1, "Unknown error", iterations_run)

    return LoopResult(3, f"Max iterations reached ({max_iter})", iterations_run)

"""Main loop engine for Ralph."""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

from ralph.core.agent import Agent, AgentResult
from ralph.core.ignore import create_spec, load_ignore_patterns
from ralph.core.pool import AgentPool
from ralph.core.prompt import assemble_prompt
from ralph.core.run_state import (
    RunState,
    delete_run_state,
    get_current_log_path,
    now_iso,
    write_run_state,
)
from ralph.core.snapshot import compare_snapshots, take_snapshot
from ralph.core.specs import discover_specs, read_spec_content
from ralph.core.state import (
    MultiSpecState,
    SpecProgress,
    Status,
    ensure_state,
    get_handoff_path,
    read_guardrails,
    read_handoff,
    read_status,
    write_done_count,
    write_handoff,
    write_history,
    write_iteration,
    write_multi_state,
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
    agent_error: str | None = None,
    agent_exit_code: int | None = None,
    crash_summary: str | None = None,
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
    ]

    if agent_error:
        lines.extend(
            [
                "",
                "--- AGENT ERROR ---",
                agent_error,
            ]
        )

    if crash_summary:
        lines.extend(
            [
                "",
                "--- CRASH DETECTED ---",
                f"Summary: {crash_summary}",
            ]
        )
        if agent_exit_code is not None:
            lines.append(f"Exit Code: {agent_exit_code}")
        lines.append(f"Output Bytes: {len(agent_output)}")

    lines.extend(
        [
            "",
            "--- STATUS ---",
            f"Signal: {status.value}",
            f"Files Changed: {len(files_changed)}",
        ]
    )

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


_CRASH_ERROR_PATTERNS = [
    r"no messages returned",
    r"econnreset",
    r"etimedout",
]


def _first_non_empty_line(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _detect_agent_crash(result: AgentResult, exhausted: bool) -> tuple[str, str | None] | None:
    if exhausted:
        return None

    output_empty = not result.output.strip()
    error_text = result.error or ""
    matched_pattern = None
    if error_text:
        for pattern in _CRASH_ERROR_PATTERNS:
            if re.search(pattern, error_text, re.IGNORECASE):
                matched_pattern = pattern
                break

    if output_empty:
        summary = "empty output from agent"
    elif result.exit_code != 0:
        summary = f"non-zero exit code ({result.exit_code})"
    elif matched_pattern:
        summary = f"stderr matched {matched_pattern}"
    else:
        return None

    return (summary, _first_non_empty_line(error_text))


def _append_crash_to_handoff(
    root: Path,
    spec_path: str,
    summary: str,
    error_summary: str | None,
    exit_code: int,
) -> None:
    content = read_handoff(root, spec_path)
    note_lines = [f"- Previous rotation crashed: {summary}"]
    note_lines.append(f"  - Exit code: {exit_code}")
    if error_summary:
        note_lines.append(f"  - Error: {error_summary}")
    note_block = "\n".join(note_lines)

    if "## Notes" in content:
        content = content.rstrip() + "\n" + note_block + "\n"
    else:
        content = content.rstrip() + "\n\n## Notes\n" + note_block + "\n"

    write_handoff(content, root, spec_path)


def run_iteration(
    iteration: int,
    max_iter: int,
    test_cmd: str | None,
    agent: Agent,
    spec_path: str,
    spec_goal: str,
    done_count: int,
    root: Path | None = None,
    timeout: int | None = 10800,
    output_file: Path | None = None,
) -> IterationResult:
    """Run a single iteration of the loop.

    Args:
        iteration: Current iteration number
        max_iter: Maximum number of iterations
        test_cmd: Optional test command to run after the iteration
        agent: The agent to use for this iteration
        root: Project root directory
        timeout: Timeout in seconds for agent invocation (default 3 hours), None for no timeout
    """
    if root is None:
        root = Path.cwd()

    # Load ignore patterns and create spec
    patterns = load_ignore_patterns(root)
    spec = create_spec(patterns)

    # Take pre-iteration snapshot
    snapshot_before = take_snapshot(root, spec)

    # Read state
    goal = spec_goal or ""
    handoff = read_handoff(root, spec_path)
    guardrails = read_guardrails(root)
    handoff_path = get_handoff_path(spec_path, root)

    # Assemble prompt
    prompt = assemble_prompt(
        iteration=iteration,
        max_iter=max_iter,
        done_count=done_count,
        goal=goal,
        handoff=handoff,
        guardrails=guardrails,
        spec_path=spec_path,
        handoff_path=handoff_path.as_posix(),
    )

    # Reset status to IDLE before invoking agent.
    # This ensures each iteration starts with a known state - if the agent doesn't
    # write a new status, we get IDLE instead of stale data from previous iteration.
    write_status(Status.IDLE, root)

    # Truncate live output log for this iteration
    if output_file is not None:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text("", encoding="utf-8")

    # Invoke agent with real-time crash pattern monitoring
    result: AgentResult = agent.invoke(
        prompt,
        timeout=timeout,
        output_file=output_file,
        crash_patterns=_CRASH_ERROR_PATTERNS,
    )

    # Parse status
    status = read_status(root)

    exhausted = agent.is_exhausted(result)
    crash_info = _detect_agent_crash(result, exhausted)
    if crash_info:
        crash_summary, error_summary = crash_info
        status = Status.ROTATE
        write_status(status, root)
        _append_crash_to_handoff(
            root=root,
            spec_path=spec_path,
            summary=crash_summary,
            error_summary=error_summary,
            exit_code=result.exit_code,
        )

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
        agent_error=result.error,
        agent_exit_code=result.exit_code,
        crash_summary=crash_info[0] if crash_info else None,
    )
    write_history(iteration, log_content, root, spec_path)

    return IterationResult(
        status=status,
        files_changed=files_changed,
        test_result=test_result,
        claude_output=result.output,
        agent_result=result,
    )


def handle_status(
    state: MultiSpecState,
    spec_index: int,
    status: Status,
    files_changed: list[str],
) -> tuple[str, int | None, MultiSpecState, int]:
    """Handle status signal and return (action, exit_code or None, new_state, spec_done_count).

    action: "continue", "exit"
    exit_code: None if continuing, otherwise the exit code
    """
    if status == Status.STUCK:
        return ("exit", 2, state, 0)

    specs = list(state.specs)
    if files_changed:
        specs = [SpecProgress(path=spec.path, done_count=0) for spec in specs]

    if status == Status.DONE:
        if not files_changed:
            current_done = specs[spec_index].done_count + 1
            if current_done > 3:
                current_done = 3
            specs[spec_index] = SpecProgress(
                path=specs[spec_index].path,
                done_count=current_done,
            )
    else:
        if specs[spec_index].done_count > 0:
            specs[spec_index] = SpecProgress(
                path=specs[spec_index].path,
                done_count=0,
            )

    updated = MultiSpecState(
        version=state.version,
        iteration=state.iteration,
        status=status,
        current_index=state.current_index,
        specs=specs,
    )

    spec_done_count = 0
    if specs and 0 <= spec_index < len(specs):
        spec_done_count = specs[spec_index].done_count

    if specs and all(spec.done_count >= 3 for spec in specs):
        return ("exit", 0, updated, spec_done_count)

    return ("continue", None, updated, spec_done_count)


def run_loop(
    max_iter: int = 20,
    test_cmd: str | None = None,
    root: Path | None = None,
    agent_pool: AgentPool | None = None,
    on_iteration_start: Callable[[int, int, int, str, str], None] | None = None,
    on_iteration_end: Callable[[int, IterationResult, int, str, str], None] | None = None,
    timeout: int | None = 10800,
) -> LoopResult:
    """Run the main Ralph loop.

    Args:
        max_iter: Maximum number of iterations
        test_cmd: Optional test command to run after each iteration
        root: Project root directory
        agent_pool: Pool of agents to use (required)
        on_iteration_start: Callback(iteration, max_iter, done_count, agent_name, spec_path)
        on_iteration_end: Callback(iteration, result, done_count, agent_name, spec_path)
        timeout: Timeout in seconds per rotation (default 3 hours), None for no timeout

    Returns:
        LoopResult with exit code, message, and iterations run
    """
    if root is None:
        root = Path.cwd()

    if agent_pool is None:
        raise ValueError("agent_pool is required")

    specs = discover_specs(root)
    if not specs:
        return LoopResult(1, "No spec files found", 0)

    state = ensure_state([spec.rel_posix for spec in specs], root)
    iteration = state.iteration
    iterations_run = 0
    started_at = now_iso()

    initial_state = RunState(
        pid=os.getpid(),
        started_at=started_at,
        iteration=iteration,
        max_iterations=max_iter,
        agent="pending",
        agent_started_at=started_at,
    )
    write_run_state(initial_state, root)

    try:
        while iteration < max_iter:
            # Check if we have any agents left
            if agent_pool.is_empty():
                return LoopResult(4, "All agents exhausted", iterations_run)

            specs = discover_specs(root)
            if not specs:
                return LoopResult(1, "No spec files found", iterations_run)

            state = ensure_state([spec.rel_posix for spec in specs], root)
            spec_map = {spec.rel_posix: spec for spec in specs}

            # Select an agent for this iteration
            agent = agent_pool.select_random()

            iteration += 1
            state = MultiSpecState(
                version=state.version,
                iteration=iteration,
                status=state.status,
                current_index=state.current_index,
                specs=state.specs,
            )
            write_multi_state(state, root)
            write_iteration(iteration, root)
            iterations_run += 1

            write_run_state(
                RunState(
                    pid=os.getpid(),
                    started_at=started_at,
                    iteration=iteration,
                    max_iterations=max_iter,
                    agent=agent.name,
                    agent_started_at=now_iso(),
                ),
                root,
            )

            if on_iteration_start:
                current_spec = state.specs[state.current_index]
                on_iteration_start(
                    iteration,
                    max_iter,
                    current_spec.done_count,
                    agent.name,
                    current_spec.path,
                )

            output_file = get_current_log_path(root)
            current_spec = state.specs[state.current_index]
            spec = spec_map[current_spec.path]
            spec_goal = read_spec_content(spec.path) or ""

            result = run_iteration(
                iteration,
                max_iter,
                test_cmd,
                agent,
                current_spec.path,
                spec_goal,
                current_spec.done_count,
                root,
                timeout,
                output_file=output_file,
            )

            # Check if agent is exhausted
            if result.agent_result and agent.is_exhausted(result.agent_result):
                agent_pool.remove(agent)
                # If this was our last agent, exit
                if agent_pool.is_empty():
                    return LoopResult(4, "All agents exhausted", iterations_run)

            action, exit_code, state, spec_done_count = handle_status(
                state,
                state.current_index,
                result.status,
                result.files_changed,
            )
            write_multi_state(state, root)
            write_done_count(spec_done_count, root)

            if on_iteration_end:
                on_iteration_end(
                    iteration,
                    result,
                    spec_done_count,
                    agent.name,
                    current_spec.path,
                )

            if action == "exit":
                if exit_code == 0:
                    return LoopResult(0, "Goal achieved!", iterations_run)
                elif exit_code == 2:
                    return LoopResult(
                        2,
                        "Ralph needs help. Check .ralph/handoffs/",
                        iterations_run,
                    )
                else:
                    return LoopResult(exit_code or 1, "Unknown error", iterations_run)

            if state.specs:
                next_index = (state.current_index + 1) % len(state.specs)
                state = MultiSpecState(
                    version=state.version,
                    iteration=state.iteration,
                    status=state.status,
                    current_index=next_index,
                    specs=state.specs,
                )
                write_multi_state(state, root)

        return LoopResult(3, f"Max iterations reached ({max_iter})", iterations_run)
    finally:
        delete_run_state(root)

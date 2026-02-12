"""Main loop engine for Ralph."""

from __future__ import annotations

import os
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
from ralph.core.specs import (
    Spec,
    discover_specs,
    read_spec_content,
    sort_specs_by_state,
    spec_content_hash,
)
from ralph.core.state import (
    MultiSpecState,
    SpecProgress,
    Status,
    ensure_state,
    get_handoff_path,
    read_guardrails,
    read_handoff,
    read_multi_state,
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
    agent_removals: tuple[tuple[str, str], ...] = ()


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


def _first_non_empty_line(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _detect_agent_crash(result: AgentResult, exhausted: bool) -> tuple[str, str | None] | None:
    if exhausted:
        return None

    failed = result.exit_code != 0
    output_empty = not result.output.strip()
    error_text = result.error or ""

    # Empty stdout is treated as a crash signal, even with exit code 0.
    if output_empty:
        summary = "empty output from agent"
    elif failed:
        summary = f"non-zero exit code ({result.exit_code})"
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
    current_hash: str | None,
) -> tuple[str, int | None, MultiSpecState, int]:
    """Handle status signal and return (action, exit_code or None, new_state, spec_done_count).

    action: "continue", "exit"
    exit_code: None if continuing, otherwise the exit code
    """
    specs = list(state.specs)
    has_file_changes = bool(files_changed)

    # Early check for invalid spec_index
    if not specs or spec_index < 0 or spec_index >= len(specs):
        # Return early with safe defaults
        updated = MultiSpecState(
            version=state.version,
            iteration=state.iteration,
            status=status,
            current_index=state.current_index,
            specs=specs,
        )
        if status == Status.STUCK:
            return ("exit", 2, updated, 0)
        return ("continue", None, updated, 0)

    if files_changed:
        # Multi-spec propagation rule:
        # only downgrade OTHER fully verified specs from 3/3 to 2/3.
        for idx, spec in enumerate(specs):
            if idx == spec_index:
                continue
            if spec.done_count >= 3:
                specs[idx] = SpecProgress(
                    path=spec.path,
                    done_count=2,
                    last_status=spec.last_status,
                    last_hash=spec.last_hash,
                    modified_files=spec.modified_files,
                )

    # Now handle the current spec based on its status
    if status == Status.DONE:
        if not files_changed:
            # Increment counter
            current_done = specs[spec_index].done_count + 1
            if current_done > 3:
                current_done = 3
            specs[spec_index] = SpecProgress(
                path=specs[spec_index].path,
                done_count=current_done,
                last_status=status.value,
                last_hash=current_hash,
                modified_files=has_file_changes,
            )
        else:
            # Files changed and status is DONE - reset to 1/3
            specs[spec_index] = SpecProgress(
                path=specs[spec_index].path,
                done_count=1,
                last_status=status.value,
                last_hash=current_hash,
                modified_files=has_file_changes,
            )
    else:
        # Non-DONE status
        if files_changed:
            # Files changed and status is non-DONE - reset to 0/3
            specs[spec_index] = SpecProgress(
                path=specs[spec_index].path,
                done_count=0,
                last_status=status.value,
                last_hash=current_hash,
                modified_files=has_file_changes,
            )
        else:
            # No files changed and status is non-DONE - keep counter unchanged
            specs[spec_index] = SpecProgress(
                path=specs[spec_index].path,
                done_count=specs[spec_index].done_count,
                last_status=status.value,
                last_hash=current_hash,
                modified_files=has_file_changes,
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

    if status == Status.STUCK:
        return ("exit", 2, updated, spec_done_count)

    if specs and all(spec.done_count >= 3 for spec in specs):
        return ("exit", 0, updated, spec_done_count)

    return ("continue", None, updated, spec_done_count)


def _get_spec_states(
    state: MultiSpecState | None,
) -> dict[str, tuple[str | None, str | None, bool, int]]:
    """Extract spec states from MultiSpecState for sorting."""
    if state is None:
        return {}
    return {
        spec.path: (spec.last_status, spec.last_hash, spec.modified_files, spec.done_count)
        for spec in state.specs
    }


def _sort_specs_for_run(specs: list[Spec], root: Path) -> list[Spec]:
    """Sort specs by priority for this run.

    New specs and modified specs come first, then non-DONE, then DONE.
    Within DONE specs, those that modified files come before those that didn't.
    """
    existing_state = read_multi_state(root)
    spec_states = _get_spec_states(existing_state)
    return sort_specs_by_state(specs, spec_states, root)


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

    # Ensure state is up to date with discovered specs
    state = ensure_state([spec.rel_posix for spec in specs], root)

    if state.specs and all(spec.done_count >= 3 for spec in state.specs):
        return LoopResult(0, "Goal achieved!", 0)

    # Sort specs by priority and select the highest priority one
    sorted_specs = _sort_specs_for_run(specs, root)
    sorted_paths = [spec.rel_posix for spec in sorted_specs]

    # Find the highest priority spec that needs work
    best_index = 0
    for path in sorted_paths:
        spec_idx = next((i for i, s in enumerate(state.specs) if s.path == path), None)
        if spec_idx is not None:
            spec_progress = state.specs[spec_idx]
            # Select first spec that isn't already at 3/3
            if spec_progress.done_count < 3:
                best_index = spec_idx
                break

    # Update current_index to the highest priority spec
    if state.current_index != best_index:
        state = MultiSpecState(
            version=state.version,
            iteration=state.iteration,
            status=state.status,
            current_index=best_index,
            specs=state.specs,
        )
        write_multi_state(state, root)
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
            if state.specs and all(spec.done_count >= 3 for spec in state.specs):
                return LoopResult(0, "Goal achieved!", iterations_run)

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

            agent_exhausted = False
            if result.agent_result and agent.is_exhausted(result.agent_result):
                reason = agent.exhaustion_reason(result.agent_result) or "exhausted"
                removals = result.agent_removals + ((agent.name, reason),)
                result = result._replace(agent_removals=removals)
                agent_pool.remove(agent)
                agent_exhausted = True

            current_hash = spec_content_hash(spec.path)
            action, exit_code, state, spec_done_count = handle_status(
                state,
                state.current_index,
                result.status,
                result.files_changed,
                current_hash,
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

            if agent_exhausted and agent_pool.is_empty():
                return LoopResult(4, "All agents exhausted", iterations_run)

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

            # Determine next spec based on focused execution rules
            if state.specs:
                previous_paths = {spec.path for spec in state.specs}
                # Re-discover specs to check for new/modified/removed files
                new_specs = discover_specs(root)
                if not new_specs:
                    return LoopResult(1, "No spec files found", iterations_run)

                # Update state with current spec discovery
                state = ensure_state([spec.rel_posix for spec in new_specs], root)

                # Sort specs by priority
                sorted_specs = _sort_specs_for_run(new_specs, root)
                sorted_paths = [spec.rel_posix for spec in sorted_specs]
                discovered_paths = {spec.rel_posix for spec in new_specs}
                added_paths = discovered_paths - previous_paths

                # Get current spec status
                current_spec_status = result.status
                current_had_changes = bool(result.files_changed)

                # Determine next spec index
                next_index = state.current_index

                # Only switch specs if current spec is DONE with no changes
                if current_spec_status == Status.DONE and not current_had_changes:
                    # Current spec finished cleanly.
                    # Find the next highest-priority spec that needs work,
                    # preferring others over current.
                    current_spec_path = state.specs[state.current_index].path
                    found_alternative = False

                    # First pass: look for other specs that need work
                    for path in sorted_paths:
                        if path == current_spec_path:
                            continue  # Skip current spec in first pass
                        sp: SpecProgress | None = next(
                            (s for s in state.specs if s.path == path), None
                        )
                        if sp and sp.done_count < 3:
                            # Found an alternative spec that needs work
                            next_index = next(
                                (i for i, s in enumerate(state.specs) if s.path == path),
                                state.current_index,
                            )
                            found_alternative = True
                            break

                    # Second pass: if no alternatives, check if current spec still needs work
                    if not found_alternative:
                        current_spec = state.specs[state.current_index]
                        if current_spec.done_count < 3:
                            # Current spec is the only one that needs work, continue with it
                            next_index = state.current_index
                else:
                    # Current spec needs more work (CONTINUE/ROTATE/STUCK or DONE with changes)
                    # Only switch if there's a completely new spec (highest priority exception)
                    for path in sorted_paths:
                        if path in added_paths:
                            # New specs always interrupt current work.
                            next_index = next(
                                (i for i, s in enumerate(state.specs) if s.path == path),
                                state.current_index,
                            )
                            break
                    # If no new specs found, stay on current spec (focused execution)

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

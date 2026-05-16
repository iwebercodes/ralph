"""Main loop engine for Ralph."""

from __future__ import annotations

import os
import subprocess  # nosec B404 - subprocess needed for test commands
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

from ralph.core.agent import Agent, AgentResult
from ralph.core.ignore import create_spec, load_ignore_patterns
from ralph.core.pool import AgentPool
from ralph.core.prompt import assemble_prompt, assemble_system_prompt
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
    parse_every_n,
    read_spec_content,
    sort_specs_by_state,
    spec_content_hash,
    split_specs,
    system_spec_eligible,
)
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
    agent_removals: tuple[tuple[str, str], ...] = ()


class LoopResult(NamedTuple):
    """Result of running the loop."""

    exit_code: int
    message: str
    iterations_run: int


def run_test_command(cmd: str) -> tuple[int, str]:
    """Run a test command and return (exit_code, output).

    Note: Uses shell=True to support complex test commands with pipes,
    redirections, and shell features. Command input is controlled by
    user configuration, not external untrusted input.
    """
    try:
        # Parse command safely while preserving shell features
        # shell=True is needed for test commands that use pipes, etc.
        result = subprocess.run(
            cmd,
            shell=True,  # nosec B602 - controlled user input, not untrusted
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


def _downgrade_done_specs(
    state: MultiSpecState, exclude_index: int | None = None
) -> MultiSpecState:
    """Downgrade any regular spec at 3/3 to 2/3.

    Applied when a spec turn (regular or system) modifies project files.
    Optionally skips ``exclude_index`` — the spec that caused the change
    when called from the regular phase. System specs aren't in ``state.specs``,
    so for the system phase call this with ``exclude_index=None``.
    """
    specs = list(state.specs)
    changed = False
    for idx, spec in enumerate(specs):
        if idx == exclude_index:
            continue
        if spec.done_count >= 3:
            specs[idx] = SpecProgress(
                path=spec.path,
                done_count=2,
                last_status=spec.last_status,
                last_hash=spec.last_hash,
                modified_files=spec.modified_files,
            )
            changed = True
    if not changed:
        return state
    return MultiSpecState(
        version=state.version,
        iteration=state.iteration,
        status=state.status,
        current_index=state.current_index,
        specs=specs,
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


def _filter_specs(specs: list[Spec], spec_filter: str | None) -> list[Spec]:
    """Filter specs by case-insensitive substring against basename."""
    if spec_filter is None:
        return specs
    needle = spec_filter.lower()
    return [spec for spec in specs if needle in spec.path.name.lower()]


def _all_specs_done(state: MultiSpecState) -> bool:
    """True when every regular spec is verified (done_count >= 3)."""
    return all(spec.done_count >= 3 for spec in state.specs)


def _select_best_index(
    state: MultiSpecState,
    prioritized_paths: list[str],
) -> int:
    """Select index of the highest-priority regular spec that still needs work.

    System specs are not in ``state.specs`` — they fire on their own schedule
    in the system phase before this selector runs.
    """
    best_index = state.current_index if 0 <= state.current_index < len(state.specs) else 0
    for path in prioritized_paths:
        spec_idx = next((i for i, s in enumerate(state.specs) if s.path == path), None)
        if spec_idx is None:
            continue
        if state.specs[spec_idx].done_count < 3:
            return spec_idx
        if best_index == state.current_index:
            best_index = spec_idx
    return best_index


def run_system_iteration(
    iteration: int,
    max_iter: int,
    agent: Agent,
    spec_path: str,
    spec_goal: str,
    period: int,
    root: Path | None = None,
    timeout: int | None = 10800,
    output_file: Path | None = None,
) -> tuple[list[str], AgentResult]:
    """Run one system spec turn.

    Builds a system-spec prompt (no IMPLEMENT/REVIEW marker, no handoff), invokes
    the agent, snapshots project files, writes a history entry, and returns
    ``(files_changed, agent_result)``. The status file written by the agent is
    intentionally ignored — system specs have no completion signal.
    """
    if root is None:
        root = Path.cwd()

    patterns = load_ignore_patterns(root)
    ignore_spec = create_spec(patterns)

    snapshot_before = take_snapshot(root, ignore_spec)

    guardrails = read_guardrails(root)
    prompt = assemble_system_prompt(
        iteration=iteration,
        max_iter=max_iter,
        period=period,
        goal=spec_goal or "",
        guardrails=guardrails,
        spec_path=spec_path,
    )

    # System specs do not produce a completion status. Reset the status file
    # so anything the agent writes is overwritten back to IDLE before the
    # regular phase reads it.
    write_status(Status.IDLE, root)

    if output_file is not None:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text("", encoding="utf-8")

    result = agent.invoke(prompt, timeout=timeout, output_file=output_file)

    # Discard whatever the agent wrote to status — the loop ignores it.
    write_status(Status.IDLE, root)

    snapshot_after = take_snapshot(root, ignore_spec)
    files_changed = compare_snapshots(snapshot_before, snapshot_after)

    log_content = format_log_entry(
        iteration=iteration,
        prompt=prompt,
        agent_output=result.output,
        agent_name=f"{agent.name} [SYSTEM]",
        status=Status.IDLE,
        files_changed=files_changed,
        test_result=None,
        agent_error=result.error,
        agent_exit_code=result.exit_code,
        crash_summary=None,
    )
    write_history(iteration, log_content, root, spec_path)

    return files_changed, result


def _select_best_index_for_specs(
    state: MultiSpecState,
    regular_specs: list[Spec],
    root: Path,
) -> int:
    """Choose the next regular spec index from the given regular-spec list."""
    if not state.specs or not regular_specs:
        return state.current_index if state.specs else 0
    paths = {spec.rel_posix for spec in regular_specs}
    spec_states = _get_spec_states(state)
    sorted_specs = sort_specs_by_state(regular_specs, spec_states, root)
    prioritized = [spec.rel_posix for spec in sorted_specs if spec.rel_posix in paths]
    return _select_best_index(state, prioritized)


def _resolve_regular_index(
    state: MultiSpecState,
    regular_specs: list[Spec],
    root: Path,
) -> int:
    """Resolve the regular spec index for this turn.

    Preserves the regular-spec focused-execution behavior: if the currently
    selected regular spec is still in-progress (done_count < 3), stay on it.
    Otherwise re-pick by priority among regular specs that still have work.
    """
    if not state.specs:
        return 0
    current_idx = state.current_index if 0 <= state.current_index < len(state.specs) else 0
    current = state.specs[current_idx]
    if current.done_count < 3:
        return current_idx
    return _select_best_index_for_specs(state, regular_specs, root)


def _run_system_phase(
    iteration: int,
    max_iter: int,
    system_specs: list[Spec],
    agent_pool: AgentPool,
    state: MultiSpecState,
    root: Path,
    timeout: int | None,
    on_system_iteration_start: (Callable[[int, int, str, str, int], None] | None),
    on_system_iteration_end: (Callable[[int, list[str], str, str, int], None] | None),
) -> tuple[MultiSpecState, bool, tuple[tuple[str, str], ...]]:
    """Run every eligible system spec for this iteration.

    Returns ``(updated_state, any_files_changed, agent_removals)``.
    When any system spec modifies project files, regular specs at 3/3 are
    downgraded to 2/3 within the same iteration so the subsequent regular
    phase sees the post-downgrade state.
    """
    any_changes = False
    removals: tuple[tuple[str, str], ...] = ()
    for sys_spec in system_specs:
        period = parse_every_n(sys_spec.rel_posix)
        if not system_spec_eligible(sys_spec.rel_posix, iteration):
            continue
        if agent_pool.is_empty():
            break
        agent = agent_pool.select_random()
        spec_goal = read_spec_content(sys_spec.path) or ""
        output_file = get_current_log_path(root)
        write_run_state(
            RunState(
                pid=os.getpid(),
                started_at=now_iso(),
                iteration=iteration,
                max_iterations=max_iter,
                agent=f"{agent.name} [SYSTEM]",
                agent_started_at=now_iso(),
            ),
            root,
        )
        if on_system_iteration_start:
            on_system_iteration_start(iteration, max_iter, agent.name, sys_spec.rel_posix, period)

        files_changed, agent_result = run_system_iteration(
            iteration=iteration,
            max_iter=max_iter,
            agent=agent,
            spec_path=sys_spec.rel_posix,
            spec_goal=spec_goal,
            period=period,
            root=root,
            timeout=timeout,
            output_file=output_file,
        )

        if agent.is_exhausted(agent_result):
            reason = agent.exhaustion_reason(agent_result) or "exhausted"
            removals = removals + ((agent.name, reason),)
            agent_pool.remove(agent)

        if files_changed:
            any_changes = True
            state = _downgrade_done_specs(state, exclude_index=None)

        if on_system_iteration_end:
            on_system_iteration_end(
                iteration, files_changed, agent.name, sys_spec.rel_posix, period
            )

    return state, any_changes, removals


def run_loop(
    max_iter: int = 20,
    test_cmd: str | None = None,
    root: Path | None = None,
    agent_pool: AgentPool | None = None,
    on_iteration_start: Callable[[int, int, int, str, str], None] | None = None,
    on_iteration_end: Callable[[int, IterationResult, int, str, str], None] | None = None,
    timeout: int | None = 10800,
    spec_filter: str | None = None,
    on_system_iteration_start: (Callable[[int, int, str, str, int], None] | None) = None,
    on_system_iteration_end: (Callable[[int, list[str], str, str, int], None] | None) = None,
) -> LoopResult:
    """Run the main Ralph loop.

    Each loop turn is a single ``iteration`` and proceeds in four steps:

    1. **Exit check** — consider regular specs only. Exit 0 if no regular spec
       exists (system specs cannot drive a loop) or all are verified at 3/3.
    2. **System phase** — for every system spec where
       ``iteration % every_n == 0``, run it in alphabetical order. File changes
       trigger the same downgrade rule as a regular spec (any regular at 3/3 →
       2/3) within this iteration.
    3. **Regular phase** — select the highest-priority regular spec and run one
       turn of it. ``handle_status`` may signal an exit (STUCK or all-done).
    4. **Advance** — the iteration counter advances by exactly one.

    Args:
        max_iter: Maximum number of iterations
        test_cmd: Optional test command to run after each regular iteration
        root: Project root directory
        agent_pool: Pool of agents to use (required)
        on_iteration_start: Callback(iteration, max_iter, done_count, agent_name, spec_path)
            fired for the regular phase only.
        on_iteration_end: Callback(iteration, result, done_count, agent_name, spec_path)
            fired for the regular phase only.
        on_system_iteration_start: Callback(iteration, max_iter, agent_name, spec_path, period)
            fired for each system spec turn.
        on_system_iteration_end: Callback(iteration, files_changed, agent_name, spec_path, period)
            fired for each system spec turn.
        timeout: Timeout in seconds per rotation (default 3 hours), None for no timeout

    Returns:
        LoopResult with exit code, message, and iterations run
    """
    if root is None:
        root = Path.cwd()

    if agent_pool is None:
        raise ValueError("agent_pool is required")

    all_specs = discover_specs(root)
    if not all_specs:
        return LoopResult(1, "No spec files found", 0)
    filtered_all = _filter_specs(all_specs, spec_filter)
    if spec_filter is not None and not filtered_all:
        return LoopResult(1, "No specs match filter criteria", 0)

    regular_specs, system_specs = split_specs(filtered_all)

    # Persisted state only tracks regular specs.
    state = ensure_state([s.rel_posix for s in regular_specs], root)

    # Exit check before any work: no regulars or all done → exit 0
    if not regular_specs:
        return LoopResult(0, "Goal achieved!", 0)
    if state.specs and _all_specs_done(state):
        return LoopResult(0, "Goal achieved!", 0)

    # Select initial best regular spec
    best_index = _select_best_index_for_specs(state, regular_specs, root)
    if state.specs and state.current_index != best_index:
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
            # Re-discover each turn so newly added specs are picked up.
            all_specs = discover_specs(root)
            if not all_specs:
                return LoopResult(1, "No spec files found", iterations_run)
            filtered_all = _filter_specs(all_specs, spec_filter)
            if spec_filter is not None and not filtered_all:
                return LoopResult(1, "No specs match filter criteria", iterations_run)
            regular_specs, system_specs = split_specs(filtered_all)

            state = ensure_state([s.rel_posix for s in regular_specs], root)

            # === Step 1: Exit check ===
            if not regular_specs:
                return LoopResult(0, "Goal achieved!", iterations_run)
            if _all_specs_done(state):
                return LoopResult(0, "Goal achieved!", iterations_run)

            if agent_pool.is_empty():
                return LoopResult(4, "All agents exhausted", iterations_run)

            # Compute this turn's iteration number — used for system spec
            # eligibility and for display.
            this_iteration = iteration + 1

            # === Step 2: System phase ===
            sys_files_changed = False
            if system_specs:
                state, sys_files_changed, sys_removals = _run_system_phase(
                    iteration=this_iteration,
                    max_iter=max_iter,
                    system_specs=system_specs,
                    agent_pool=agent_pool,
                    state=state,
                    root=root,
                    timeout=timeout,
                    on_system_iteration_start=on_system_iteration_start,
                    on_system_iteration_end=on_system_iteration_end,
                )
                # System phase may have downgraded specs — persist before
                # the regular phase reads state.
                if sys_files_changed:
                    write_multi_state(state, root)
                if agent_pool.is_empty():
                    # No agents left after the system phase.
                    return LoopResult(4, "All agents exhausted", iterations_run)

                # Surface system-spec agent removals via the next regular result.
                pending_removals = sys_removals
            else:
                pending_removals = ()

            # === Step 3: Regular phase ===
            # If the system phase downgraded specs, re-prioritize so the
            # regular phase picks up the new priority landscape. Otherwise
            # preserve focused execution: stay on the current spec while it
            # still has work.
            if sys_files_changed:
                regular_index = _select_best_index_for_specs(state, regular_specs, root)
            else:
                regular_index = _resolve_regular_index(state, regular_specs, root)
            if state.specs and state.current_index != regular_index:
                state = MultiSpecState(
                    version=state.version,
                    iteration=state.iteration,
                    status=state.status,
                    current_index=regular_index,
                    specs=state.specs,
                )
                write_multi_state(state, root)

            agent = agent_pool.select_random()

            # Advance the iteration counter for this turn.
            iteration = this_iteration
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

            current_spec = state.specs[state.current_index]
            regular_map = {s.rel_posix: s for s in regular_specs}
            spec = regular_map[current_spec.path]
            spec_goal = read_spec_content(spec.path) or ""

            if on_iteration_start:
                on_iteration_start(
                    iteration,
                    max_iter,
                    current_spec.done_count,
                    agent.name,
                    current_spec.path,
                )

            output_file = get_current_log_path(root)
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
                pending_removals = pending_removals + ((agent.name, reason),)
                agent_pool.remove(agent)
                agent_exhausted = True

            if pending_removals:
                result = result._replace(agent_removals=result.agent_removals + pending_removals)

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

            # Apply focused-execution rules to pick the regular spec for the
            # NEXT turn. System specs do not participate here — they fire on
            # their own schedule in step 2.
            all_specs_after = discover_specs(root)
            if not all_specs_after:
                return LoopResult(1, "No spec files found", iterations_run)
            filtered_after = _filter_specs(all_specs_after, spec_filter)
            if spec_filter is not None and not filtered_after:
                return LoopResult(1, "No specs match filter criteria", iterations_run)
            regular_after, _system_after = split_specs(filtered_after)
            previous_regular_paths = {spec.path for spec in state.specs}
            state = ensure_state([s.rel_posix for s in regular_after], root)

            sorted_regular = sort_specs_by_state(regular_after, _get_spec_states(state), root)
            sorted_paths = [spec.rel_posix for spec in sorted_regular]
            discovered_paths = {spec.rel_posix for spec in regular_after}
            added_paths = discovered_paths - previous_regular_paths

            if not state.specs:
                # All regular specs removed mid-run.
                continue

            current_spec_after = state.specs[state.current_index]
            current_status = result.status
            current_had_changes = bool(result.files_changed)

            next_index = state.current_index
            if (
                current_status == Status.DONE
                and not current_had_changes
                and current_spec_after.done_count >= 3
            ):
                # Current spec is fully verified — look for another that needs work.
                for path in sorted_paths:
                    if path == current_spec_after.path:
                        continue
                    alt = next((s for s in state.specs if s.path == path), None)
                    if alt and alt.done_count < 3:
                        next_index = next(
                            (i for i, s in enumerate(state.specs) if s.path == path),
                            state.current_index,
                        )
                        break
            else:
                # New specs always interrupt focused execution.
                for path in sorted_paths:
                    if path in added_paths:
                        next_index = next(
                            (i for i, s in enumerate(state.specs) if s.path == path),
                            state.current_index,
                        )
                        break

            if state.current_index != next_index:
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

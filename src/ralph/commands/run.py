"""ralph run command."""

from __future__ import annotations

import signal
import sys
import time
from pathlib import Path

import typer

from ralph.commands.global_flags import about_callback, version_callback
from ralph.core.agent import Agent, ClaudeAgent, CodexAgent
from ralph.core.loop import IterationResult, run_loop
from ralph.core.pool import AgentPool
from ralph.core.prompt import assemble_prompt
from ralph.core.run_state import delete_run_state, is_pid_alive, read_run_state
from ralph.core.specs import Spec, discover_specs, read_spec_content
from ralph.core.state import (
    get_handoff_path,
    is_initialized,
    read_guardrails,
    read_handoff,
    read_state,
)
from ralph.output.console import Console


def format_duration(seconds: float) -> str:
    """Format duration as human-readable string."""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _filter_specs(spec_filter: str | None, specs: list[Spec]) -> list[Spec]:
    """Filter discovered specs by case-insensitive basename substring."""
    if spec_filter is None:
        return specs
    needle = spec_filter.lower()
    return [spec for spec in specs if needle in spec.path.name.lower()]


def run(
    version: bool = typer.Option(
        False,
        "--version",
        is_eager=True,
        hidden=True,
        callback=version_callback,
    ),
    about: bool = typer.Option(
        False,
        "--about",
        is_eager=True,
        hidden=True,
        callback=about_callback,
    ),
    max_iterations: int = typer.Option(20, "--max", "-m", help="Maximum number of iterations"),
    agents: str | None = typer.Option(
        None, "--agents", "-a", help="Comma-separated agent names (e.g., 'claude' or 'codex')"
    ),
    timeout: int | None = typer.Option(
        10800, "--timeout", help="Timeout per rotation in seconds (default: 3 hours)"
    ),
    no_timeout: bool = typer.Option(
        False, "--no-timeout", help="Disable timeout entirely (run until completion)"
    ),
    no_color: bool = typer.Option(False, "--no-color", help="Disable colored output"),
    filter_spec: str | None = typer.Option(
        None, "--filter", help="Filter specs by substring match in filename"
    ),
    debug_prompt: bool = typer.Option(
        False,
        "--debug-prompt",
        help="Output the fully constructed prompt to stdout instead of executing agents, then exit",
    ),
) -> None:
    """Execute the Ralph loop until completion or max iterations."""
    root = Path.cwd()
    console = Console(no_color=no_color)

    # Prerequisites check
    if not is_initialized(root):
        console.error("Ralph not initialized", "Run: ralph init")
        raise typer.Exit(1)

    specs = discover_specs(root)
    if not specs:
        hint = """Ralph needs a spec file to run.

Supported locations:
  - PROMPT.md in the project root
  - .ralph/specs/**/*.spec.md
  - specs/**/*.spec.md

See docs: docs/writing-prompts.md"""
        console.error("No spec files found", hint)
        raise typer.Exit(1)

    specs = _filter_specs(filter_spec, specs)
    if filter_spec is not None and not specs:
        all_specs = discover_specs(root)
        console.error(
            f"No specs match filter: '{filter_spec}'",
            f"Available specs: {', '.join(s.path.name for s in all_specs)}",
        )
        raise typer.Exit(1)

    for spec in specs:
        content = read_spec_content(spec.path)
        if not content:
            console.error(
                f"Spec file is empty: {spec.rel_posix}",
                "Add a goal and success criteria, then run: ralph run",
            )
            raise typer.Exit(1)

    existing_run = read_run_state(root)
    if existing_run:
        alive = is_pid_alive(existing_run.pid)
        if alive:
            console.error(
                f"Ralph is already running (PID {existing_run.pid})",
                "Use: ralph inspect",
            )
            raise typer.Exit(1)
        delete_run_state(root)

    # Handle debug-prompt mode
    if debug_prompt:
        # Use the first spec (or only spec if filtered)
        spec = specs[0]
        spec_path = spec.rel_posix
        spec_goal = read_spec_content(spec.path) or ""

        # Read current state
        state = read_state(root)
        iteration = state.iteration + 1
        done_count = state.done_count

        # Read handoff and guardrails
        handoff = read_handoff(root, spec_path)
        guardrails = read_guardrails(root)
        handoff_path = get_handoff_path(spec_path, root)

        # Assemble the prompt
        prompt = assemble_prompt(
            iteration=iteration,
            max_iter=max_iterations,
            done_count=done_count,
            goal=spec_goal,
            handoff=handoff,
            guardrails=guardrails,
            spec_path=spec_path,
            handoff_path=handoff_path.as_posix(),
        )

        # Output the prompt to stdout and exit
        console.print(prompt)
        raise typer.Exit(0)

    # Build agent pool from available agents
    all_agents: list[Agent] = [ClaudeAgent(), CodexAgent()]

    # Filter by --agents option if specified
    if agents is not None:
        allowed = [name.strip().lower() for name in agents.split(",") if name.strip()]

        if not allowed:
            console.error(
                "No agent names provided",
                "Use --agents claude or --agents claude,codex",
            )
            raise typer.Exit(1)

        # Validate: reject unknown agent names
        known = {a.name.lower() for a in all_agents}
        unknown = set(allowed) - known
        if unknown:
            available_names = ", ".join(a.name for a in all_agents)
            console.error(
                f"Unknown agent: {', '.join(sorted(unknown))}",
                f"Available agents: {available_names}",
            )
            raise typer.Exit(1)

        filtered = [a for a in all_agents if a.name.lower() in allowed]
    else:
        filtered = all_agents

    # Check availability
    available = [a for a in filtered if a.is_available()]

    if not available:
        if agents:
            # User specified agents but none are available
            unavailable = [a.name for a in filtered if not a.is_available()]
            console.error(
                f"Specified agent(s) not available: {', '.join(unavailable)}",
                "Check that the CLI tool is installed and in PATH",
            )
        else:
            hint = """Ralph requires at least one AI agent CLI to be installed.

Supported agents:
  - Claude CLI: https://claude.ai/download
  - Codex CLI: https://openai.com/codex

After installing, verify with: claude --version or codex --version"""
            console.error("No AI agents available", hint)
        raise typer.Exit(1)

    pool = AgentPool(available)

    # Handle Ctrl+C gracefully
    interrupted = False

    def handle_interrupt(signum: int, frame: object) -> None:
        nonlocal interrupted
        interrupted = True
        console.print("\n\nInterrupted. State saved.")
        state = read_state(root)
        console.print(f"\n  State: iteration {state.iteration} (interrupted)")
        console.print("\nTo resume: ralph run")
        console.print("To reset: ralph reset")
        sys.exit(130)

    signal.signal(signal.SIGINT, handle_interrupt)

    start_time = time.time()

    # Show banner at start
    console.banner()

    # Track iteration start time
    iteration_start_time: float | None = None

    def on_iteration_start(
        iteration: int, max_iter: int, done_count: int, agent_name: str, spec_path: str
    ) -> None:
        nonlocal iteration_start_time
        iteration_start_time = time.time()
        console.working(done_count, agent_name)
        console.iteration_info(iteration, max_iter, done_count, spec_path)

    def on_iteration_end(
        iteration: int,
        result: IterationResult,
        done_count: int,
        agent_name: str,
        spec_path: str,
    ) -> None:
        # Calculate duration
        duration = None
        if iteration_start_time is not None:
            duration = time.time() - iteration_start_time

        console.rotation_complete(
            result.status,
            result.files_changed,
            done_count,
            result.agent_removals,
            duration,
        )

        console.close_iteration()

    # Handle timeout options
    effective_timeout: int | None = None if no_timeout else timeout

    result = run_loop(
        max_iter=max_iterations,
        test_cmd=None,
        root=root,
        agent_pool=pool,
        on_iteration_start=on_iteration_start,
        on_iteration_end=on_iteration_end,
        timeout=effective_timeout,
        spec_filter=filter_spec,
    )

    duration = time.time() - start_time
    duration_str = format_duration(duration)

    if result.exit_code == 0:
        console.goal_achieved(result.iterations_run, duration_str)
        raise typer.Exit(0)
    elif result.exit_code == 2:
        console.stuck()
        raise typer.Exit(2)
    elif result.exit_code == 3:
        console.max_iterations(max_iterations)
        raise typer.Exit(3)
    elif result.exit_code == 4:
        console.all_agents_exhausted()
        raise typer.Exit(4)
    else:
        console.error(result.message)
        raise typer.Exit(1)

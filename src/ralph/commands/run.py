"""ralph run command."""

from __future__ import annotations

import signal
import sys
import time
from pathlib import Path

import typer

from ralph.core.claude import is_claude_available
from ralph.core.loop import IterationResult, run_loop
from ralph.core.state import is_initialized, read_prompt_md, read_state
from ralph.output.console import Console


def format_duration(seconds: float) -> str:
    """Format duration as human-readable string."""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def run(
    max_iterations: int = typer.Option(20, "--max", "-m", help="Maximum number of iterations"),
    test_cmd: str | None = typer.Option(
        None, "--test-cmd", "-t", help="Command to run after each iteration"
    ),
    no_color: bool = typer.Option(False, "--no-color", help="Disable colored output"),
) -> None:
    """Execute the Ralph loop until completion or max iterations."""
    root = Path.cwd()
    console = Console(no_color=no_color)

    # Prerequisites check
    if not is_initialized(root):
        console.error("Ralph not initialized", "Run: ralph init")
        raise typer.Exit(1)

    prompt = read_prompt_md(root)
    if not prompt:
        hint = """Ralph needs a PROMPT.md file in the current directory.
Create one with your goal, then run: ralph run

Example PROMPT.md:
  # Goal
  Implement user authentication with JWT tokens.

  # Success Criteria
  - [ ] Users can register with email/password
  - [ ] Users can log in and receive JWT token"""
        console.error("PROMPT.md not found or empty", hint)
        raise typer.Exit(1)

    if not is_claude_available():
        hint = """Ralph requires the Claude CLI to be installed.
Install it from: https://claude.ai/download

After installing, verify with: claude --version"""
        console.error("claude CLI not found", hint)
        raise typer.Exit(1)

    # Handle Ctrl+C gracefully
    interrupted = False

    def handle_interrupt(signum: int, frame: object) -> None:
        nonlocal interrupted
        interrupted = True
        typer.echo("\n\nInterrupted. State saved.")
        state = read_state(root)
        typer.echo(f"\n  State: iteration {state.iteration} (interrupted)")
        typer.echo("\nTo resume: ralph run")
        typer.echo("To reset: ralph reset")
        sys.exit(130)

    signal.signal(signal.SIGINT, handle_interrupt)

    start_time = time.time()

    # Show banner at start
    console.banner()

    def on_iteration_start(iteration: int, max_iter: int, done_count: int) -> None:
        console.working(done_count)
        console.iteration_info(iteration, max_iter, done_count)

    def on_iteration_end(iteration: int, result: IterationResult, done_count: int) -> None:
        console.rotation_complete(
            result.status,
            result.files_changed,
            done_count,
        )

        if result.test_result:
            exit_code, _ = result.test_result
            console.test_result(
                test_cmd or "",
                exit_code,
                passed=(exit_code == 0),
            )

        console.close_iteration()

    result = run_loop(
        max_iter=max_iterations,
        test_cmd=test_cmd,
        root=root,
        on_iteration_start=on_iteration_start,
        on_iteration_end=on_iteration_end,
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
    else:
        console.error(result.message)
        raise typer.Exit(1)

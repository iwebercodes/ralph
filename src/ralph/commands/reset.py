"""ralph reset command."""

from __future__ import annotations

import shutil
from pathlib import Path

import typer

from ralph.commands.global_flags import about_callback, version_callback
from ralph.core.run_state import delete_run_state, is_pid_alive, read_run_state
from ralph.core.state import (
    GUARDRAILS_TEMPLATE,
    HANDOFF_DIR,
    HANDOFF_TEMPLATE,
    MultiSpecState,
    SpecProgress,
    Status,
    get_handoff_path,
    get_history_dir,
    get_ralph_dir,
    is_initialized,
    read_multi_state,
    write_done_count,
    write_guardrails,
    write_handoff,
    write_iteration,
    write_multi_state,
    write_status,
)
from ralph.output.console import Console


def reset(
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
    reset_guardrails: bool = typer.Option(
        False, "--reset-guardrails", help="Reset guardrails.md to template"
    ),
    reset_history: bool = typer.Option(False, "--reset-history", help="Clear history/ directory"),
    reset_counter: bool = typer.Option(
        False, "--reset-counter", help="Reset verification counter (done_count) to 0"
    ),
    reset_handoffs: bool = typer.Option(
        False, "--reset-handoffs", help="Reset all handoff files to template"
    ),
) -> None:
    """Reset Ralph iteration counter to start a new rotation cycle."""
    root = Path.cwd()
    console = Console()

    if not is_initialized(root):
        console.error("Ralph not initialized", "Run: ralph init")
        raise typer.Exit(1)

    run_state = read_run_state(root)
    if run_state is not None and is_pid_alive(run_state.pid):
        console.error(
            f"Ralph is currently running (PID {run_state.pid})",
            "Stop the active run before resetting",
        )
        raise typer.Exit(1)
    if run_state is not None:
        delete_run_state(root)

    ralph_dir = get_ralph_dir(root)

    # Preserve spec priority state (last_status, last_hash, modified_files) across reset
    existing_state = read_multi_state(root)
    preserved_specs: list[SpecProgress] = []
    if existing_state:
        for spec in existing_state.specs:
            preserved_specs.append(
                SpecProgress(
                    path=spec.path,
                    done_count=0 if reset_counter else spec.done_count,  # Reset or preserve
                    last_status=spec.last_status,  # Preserve for priority sorting
                    last_hash=spec.last_hash,  # Preserve for modification detection
                    modified_files=spec.modified_files,  # Preserve for priority sorting
                )
            )

    # Always reset iteration and status
    write_iteration(0, root)

    # Read the current done_count value for preservation
    from ralph.core.state import read_done_count

    current_done_count = read_done_count(root)
    write_done_count(0 if reset_counter else current_done_count, root)

    write_status(Status.IDLE, root)

    # Preserve legacy handoff by default
    if reset_handoffs:
        write_handoff(HANDOFF_TEMPLATE, root)

    write_multi_state(
        MultiSpecState(
            version=1,
            iteration=0,
            status=Status.IDLE,
            current_index=0,
            specs=preserved_specs,
        ),
        root,
    )

    # Remove snapshot files
    for snapshot_file in ralph_dir.glob("snapshot_*"):
        snapshot_file.unlink()

    # Handle guardrails - preserve by default
    guardrails_reset = False
    if reset_guardrails:
        write_guardrails(GUARDRAILS_TEMPLATE, root)
        guardrails_reset = True

    # Handle history - preserve by default
    history_cleared = False
    history_dir = get_history_dir(root)
    if reset_history and history_dir.exists():
        shutil.rmtree(history_dir)
        history_dir.mkdir()
        history_cleared = True

    # Handle per-spec handoffs - preserve by default
    handoffs_reset = False
    handoffs_dir = get_ralph_dir(root) / HANDOFF_DIR
    if reset_handoffs:
        handoffs_dir.mkdir(parents=True, exist_ok=True)
        for handoff_file in handoffs_dir.glob("*.md"):
            handoff_file.write_text(HANDOFF_TEMPLATE, encoding="utf-8")
        for spec in preserved_specs:
            get_handoff_path(spec.path, root).write_text(HANDOFF_TEMPLATE, encoding="utf-8")
        handoffs_reset = True

    console.print("Reset complete.")
    console.print("  Iteration: 0")
    console.print("  Status: IDLE")

    # Show what was reset and what was preserved
    console.print(f"  Guardrails: {'reset to template' if guardrails_reset else 'preserved'}")
    console.print(f"  History: {'cleared' if history_cleared else 'preserved'}")
    console.print(f"  Counters: {'reset to 0' if reset_counter else 'preserved'}")
    console.print(f"  Handoffs: {'reset to template' if handoffs_reset else 'preserved'}")

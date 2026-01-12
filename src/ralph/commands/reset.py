"""ralph reset command."""

from __future__ import annotations

import shutil
from pathlib import Path

import typer

from ralph.core.state import (
    GUARDRAILS_TEMPLATE,
    HANDOFF_TEMPLATE,
    Status,
    get_history_dir,
    get_ralph_dir,
    is_initialized,
    write_done_count,
    write_guardrails,
    write_handoff,
    write_iteration,
    write_status,
)
from ralph.output.console import Console


def reset(
    keep_guardrails: bool = typer.Option(False, "--keep-guardrails", help="Preserve guardrails.md"),
    keep_history: bool = typer.Option(False, "--keep-history", help="Preserve history/ directory"),
) -> None:
    """Reset Ralph state to start fresh."""
    root = Path.cwd()
    console = Console()

    if not is_initialized(root):
        console.error("Ralph not initialized", "Run: ralph init")
        raise typer.Exit(1)

    ralph_dir = get_ralph_dir(root)

    # Reset state files
    write_iteration(0, root)
    write_done_count(0, root)
    write_status(Status.IDLE, root)
    write_handoff(HANDOFF_TEMPLATE, root)

    # Remove snapshot files
    for snapshot_file in ralph_dir.glob("snapshot_*"):
        snapshot_file.unlink()

    # Handle guardrails
    guardrails_preserved = False
    if keep_guardrails:
        guardrails_preserved = True
    else:
        write_guardrails(GUARDRAILS_TEMPLATE, root)

    # Handle history
    history_preserved = False
    history_dir = get_history_dir(root)
    if keep_history:
        history_preserved = True
    elif history_dir.exists():
        shutil.rmtree(history_dir)
        history_dir.mkdir()

    typer.echo("Reset complete.")
    typer.echo("  Iteration: 0")
    typer.echo("  Status: IDLE")
    typer.echo(f"  Guardrails: {'preserved' if guardrails_preserved else 'cleared'}")
    typer.echo(f"  History: {'preserved' if history_preserved else 'cleared'}")

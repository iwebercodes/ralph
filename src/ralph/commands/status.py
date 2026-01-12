"""ralph status command."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from ralph.core.state import is_initialized, read_prompt_md, read_state
from ralph.output.console import Console


def status(
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Show current Ralph state without running anything."""
    root = Path.cwd()
    console = Console()

    if not is_initialized(root):
        if as_json:
            typer.echo(json.dumps({"initialized": False}))
        else:
            console.error("Ralph not initialized", "Run: ralph init")
        raise typer.Exit(1)

    state = read_state(root)
    prompt = read_prompt_md(root)
    goal_preview = ""
    if prompt:
        # Get first non-empty, non-header line as preview
        for line in prompt.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                goal_preview = line[:60]
                if len(line) > 60:
                    goal_preview += "..."
                break

    if as_json:
        data = {
            "initialized": True,
            "iteration": state.iteration,
            "max_iterations": 20,  # Default, could be stored
            "status": state.status.value,
            "done_count": state.done_count,
            "goal_preview": goal_preview,
        }
        typer.echo(json.dumps(data, indent=2))
    else:
        console.status_display(
            iteration=state.iteration,
            max_iter=20,
            status=state.status,
            done_count=state.done_count,
            goal_preview=goal_preview if goal_preview else None,
        )

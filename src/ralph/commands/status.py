"""ralph status command."""

from __future__ import annotations

from pathlib import Path

import typer

from ralph.commands.global_flags import about_callback, version_callback
from ralph.core.specs import discover_specs
from ralph.core.state import ensure_state, is_initialized, read_prompt_md, read_state
from ralph.output.console import Console


def status(
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
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Show current Ralph state without running anything."""
    root = Path.cwd()
    console = Console()

    if not is_initialized(root):
        if as_json:
            console.json({"error": "Ralph not initialized"})
        else:
            console.error("Ralph not initialized", "Run: ralph init")
        raise typer.Exit(1)

    state = read_state(root)
    goal_preview = ""
    spec_items: list[dict[str, str]] = []
    prompt_content = read_prompt_md(root) or ""
    for line in prompt_content.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            goal_preview = line[:60]
            if len(line) > 60:
                goal_preview += "..."
            break

    specs = discover_specs(root)
    if specs:
        synced_state = ensure_state([spec.rel_posix for spec in specs], root)
        for spec_progress in synced_state.specs:
            status = spec_progress.last_status or (
                "DONE" if spec_progress.done_count >= 3 else "IDLE"
            )
            spec_items.append({"path": spec_progress.path, "status": status})

    if as_json:
        data = {
            "iteration": state.iteration,
            "max_iterations": 20,  # Default, could be stored
            "status": state.status.value,
            "done_count": state.done_count,
            "goal": goal_preview,
            "specs": spec_items,
        }
        console.json(data)
    else:
        console.status_display(
            iteration=state.iteration,
            max_iter=20,
            status=state.status,
            done_count=state.done_count,
            goal_preview=goal_preview if goal_preview else None,
        )

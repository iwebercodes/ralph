"""ralph status command."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from ralph.core.specs import discover_specs, read_spec_content
from ralph.core.state import ensure_state, is_initialized, read_state
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
    goal_preview = ""
    specs = discover_specs(root)
    if specs:
        synced_state = ensure_state([spec.rel_posix for spec in specs], root)
        if synced_state.specs and 0 <= synced_state.current_index < len(synced_state.specs):
            current_path = synced_state.specs[synced_state.current_index].path
            spec_map = {spec.rel_posix: spec for spec in specs}
            spec = spec_map.get(current_path)
            if spec:
                content = read_spec_content(spec.path) or ""
                for line in content.splitlines():
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

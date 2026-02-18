"""ralph inspect command."""

from __future__ import annotations

import shutil
import subprocess  # nosec B404 - subprocess needed for tail command
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import typer

from ralph.commands.global_flags import about_callback, version_callback
from ralph.core.run_state import get_current_log_path, is_pid_alive, read_run_state
from ralph.core.state import is_initialized, read_status
from ralph.output.console import Console


def _format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _seconds_since(timestamp: str) -> float | None:
    try:
        dt = datetime.fromisoformat(timestamp)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds()


def _tail_current_log(path: Path) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")

    tail_path = shutil.which("tail")
    if tail_path:
        subprocess.run([tail_path, "-f", str(path)], check=False)  # nosec B603 - controlled input
        return

    with path.open("r", encoding="utf-8") as handle:
        handle.seek(0, 2)
        while True:
            line = handle.readline()
            if line:
                sys.stdout.write(line)
                sys.stdout.flush()
            else:
                time.sleep(0.2)


def inspect(
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
    follow: bool = typer.Option(
        False,
        "--follow",
        "-f",
        help="After showing status, tail the live agent output log",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Output machine-readable JSON for scripting",
    ),
) -> None:
    """Show whether Ralph is currently running and its live status."""
    root = Path.cwd()
    console = Console()

    if not is_initialized(root):
        if as_json:
            console.json({"error": "Ralph not initialized"})
        else:
            console.error("Ralph not initialized", "Run: ralph init")
        raise typer.Exit(1)

    run_state = read_run_state(root)
    if run_state is None or not is_pid_alive(run_state.pid):
        if as_json:
            console.json({"running": False})
        else:
            console.inspect_not_running()
        if follow:
            _tail_current_log(get_current_log_path(root))
        raise typer.Exit(0)

    started_seconds = _seconds_since(run_state.started_at)
    agent_seconds = _seconds_since(run_state.agent_started_at)
    runtime = _format_duration(started_seconds) if started_seconds is not None else "unknown"
    status = read_status(root).value

    if as_json:
        data = {
            "running": True,
            "pid": run_state.pid,
            "iteration": run_state.iteration,
            "max_iterations": run_state.max_iterations,
            "status": status,
            "runtime": runtime,
            "current_agent": run_state.agent.lower(),
        }
        console.json(data)
    else:
        started_display = (
            _format_duration(started_seconds) + " ago" if started_seconds is not None else "unknown"
        )
        agent_display = _format_duration(agent_seconds) if agent_seconds is not None else "unknown"
        console.inspect_running(
            pid=run_state.pid,
            started_display=started_display,
            iteration=run_state.iteration,
            max_iterations=run_state.max_iterations,
            status=status,
            agent=run_state.agent,
            agent_display=agent_display,
        )

    if follow:
        _tail_current_log(get_current_log_path(root))

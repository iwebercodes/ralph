"""ralph history command."""

from __future__ import annotations

import re
from pathlib import Path

import typer

from ralph.core.state import get_history_dir, get_history_file, is_initialized
from ralph.output.console import Console


def parse_log_summary(content: str) -> tuple[str | None, str | None, int]:
    """Parse a log file for summary info.

    Returns (timestamp, status, files_changed_count)
    """
    timestamp = None
    status = None
    files_changed = 0

    # Look for timestamp in header
    timestamp_match = re.search(r"RALPH ROTATION \d+ - (\S+)", content)
    if timestamp_match:
        timestamp = timestamp_match.group(1)

    # Look for status signal
    status_match = re.search(r"Signal: (\w+)", content)
    if status_match:
        status = status_match.group(1)

    # Look for files changed count
    files_match = re.search(r"Files Changed: (\d+)", content)
    if files_match:
        files_changed = int(files_match.group(1))

    return timestamp, status, files_changed


def history(
    rotation: int | None = typer.Argument(None, help="Rotation number to view"),
    list_all: bool = typer.Option(False, "--list", "-l", help="List all rotations with summary"),
    tail: int | None = typer.Option(None, "--tail", "-n", help="Show last N lines of log"),
) -> None:
    """View logs from previous rotations."""
    root = Path.cwd()
    console = Console()

    if not is_initialized(root):
        console.error("Ralph not initialized", "Run: ralph init")
        raise typer.Exit(1)

    history_dir = get_history_dir(root)
    if not history_dir.exists():
        console.error("No history available", "Run ralph run first to create history")
        raise typer.Exit(1)

    log_files = sorted(history_dir.glob("*.log"))
    if not log_files:
        console.error("No history available", "Run ralph run first to create history")
        raise typer.Exit(1)

    if list_all:
        # Build entries list for console method
        entries: list[tuple[int, str | None, str | None, int, bool]] = []
        for log_file in log_files:
            rot_num = int(log_file.stem)
            content = log_file.read_text()
            timestamp, status, files_changed = parse_log_summary(content)

            # Check if this is the final complete entry
            is_complete = False
            if status == "DONE" and rot_num == len(log_files):
                done_count = 0
                for lf in reversed(log_files):
                    lf_content = lf.read_text()
                    _, lf_status, lf_changes = parse_log_summary(lf_content)
                    if lf_status == "DONE" and lf_changes == 0:
                        done_count += 1
                    else:
                        break
                if done_count >= 3:
                    is_complete = True

            entries.append((rot_num, timestamp, status, files_changed, is_complete))

        console.history_list(entries)
        return

    # Determine which rotation to show
    if rotation is not None:
        log_file = get_history_file(rotation, root)
        if not log_file.exists():
            console.error(
                f"Rotation {rotation} not found", "Use ralph history --list to see available"
            )
            raise typer.Exit(1)
    else:
        # Show most recent
        log_file = log_files[-1]
        rotation = int(log_file.stem)

    content = log_file.read_text()

    if tail:
        lines = content.splitlines()
        content = "\n".join(lines[-tail:])

    typer.echo(f"Ralph History - Rotation {rotation}")
    typer.echo("\u2501" * 52)
    typer.echo(content)

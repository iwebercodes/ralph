"""State file management for Ralph."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import NamedTuple

RALPH_DIR = ".ralph"
HANDOFF_FILE = "handoff.md"
GUARDRAILS_FILE = "guardrails.md"
STATUS_FILE = "status"
ITERATION_FILE = "iteration"
DONE_COUNT_FILE = "done_count"
SNAPSHOT_PREV_FILE = "snapshot_prev"
SNAPSHOT_CURR_FILE = "snapshot_curr"
HISTORY_DIR = "history"


class Status(Enum):
    """Status signals for the Ralph loop."""

    IDLE = "IDLE"
    CONTINUE = "CONTINUE"
    ROTATE = "ROTATE"
    DONE = "DONE"
    STUCK = "STUCK"


class RalphState(NamedTuple):
    """Current state of a Ralph loop."""

    iteration: int
    done_count: int
    status: Status


HANDOFF_TEMPLATE = """# Handoff

## Completed

## In Progress

## Next Steps

## Notes
"""

GUARDRAILS_TEMPLATE = """# Guardrails
"""

PROMPT_TEMPLATE = """# Goal

Describe what you want to accomplish.

# Context

Any relevant background information.

# Success Criteria

- [ ] Criterion 1
- [ ] Criterion 2

# Constraints

Any limitations or requirements.
"""


def get_ralph_dir(root: Path | None = None) -> Path:
    """Get the .ralph directory path."""
    if root is None:
        root = Path.cwd()
    return root / RALPH_DIR


def is_initialized(root: Path | None = None) -> bool:
    """Check if Ralph is initialized in the given directory."""
    return get_ralph_dir(root).exists()


def read_file(path: Path, default: str = "") -> str:
    """Read a file, returning default if it doesn't exist."""
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return default


def write_file(path: Path, content: str) -> None:
    """Write content to a file, creating parent directories if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read_iteration(root: Path | None = None) -> int:
    """Read the current iteration number."""
    ralph_dir = get_ralph_dir(root)
    content = read_file(ralph_dir / ITERATION_FILE, "0")
    try:
        return int(content)
    except ValueError:
        return 0


def write_iteration(iteration: int, root: Path | None = None) -> None:
    """Write the iteration number."""
    ralph_dir = get_ralph_dir(root)
    write_file(ralph_dir / ITERATION_FILE, str(iteration))


def read_done_count(root: Path | None = None) -> int:
    """Read the done count."""
    ralph_dir = get_ralph_dir(root)
    content = read_file(ralph_dir / DONE_COUNT_FILE, "0")
    try:
        return int(content)
    except ValueError:
        return 0


def write_done_count(count: int, root: Path | None = None) -> None:
    """Write the done count."""
    ralph_dir = get_ralph_dir(root)
    write_file(ralph_dir / DONE_COUNT_FILE, str(count))


def read_status(root: Path | None = None) -> Status:
    """Read the current status."""
    ralph_dir = get_ralph_dir(root)
    content = read_file(ralph_dir / STATUS_FILE, "IDLE").upper()
    try:
        return Status(content)
    except ValueError:
        return Status.CONTINUE


def write_status(status: Status, root: Path | None = None) -> None:
    """Write the status."""
    ralph_dir = get_ralph_dir(root)
    write_file(ralph_dir / STATUS_FILE, status.value)


def read_state(root: Path | None = None) -> RalphState:
    """Read the complete Ralph state."""
    return RalphState(
        iteration=read_iteration(root),
        done_count=read_done_count(root),
        status=read_status(root),
    )


def read_handoff(root: Path | None = None) -> str:
    """Read the handoff file content."""
    ralph_dir = get_ralph_dir(root)
    return read_file(ralph_dir / HANDOFF_FILE, HANDOFF_TEMPLATE)


def write_handoff(content: str, root: Path | None = None) -> None:
    """Write the handoff file."""
    ralph_dir = get_ralph_dir(root)
    write_file(ralph_dir / HANDOFF_FILE, content)


def read_guardrails(root: Path | None = None) -> str:
    """Read the guardrails file content."""
    ralph_dir = get_ralph_dir(root)
    return read_file(ralph_dir / GUARDRAILS_FILE, GUARDRAILS_TEMPLATE)


def write_guardrails(content: str, root: Path | None = None) -> None:
    """Write the guardrails file."""
    ralph_dir = get_ralph_dir(root)
    write_file(ralph_dir / GUARDRAILS_FILE, content)


def get_history_dir(root: Path | None = None) -> Path:
    """Get the history directory path."""
    return get_ralph_dir(root) / HISTORY_DIR


def get_history_file(iteration: int, root: Path | None = None) -> Path:
    """Get the path for a specific iteration's log file."""
    return get_history_dir(root) / f"{iteration:03d}.log"


def write_history(iteration: int, content: str, root: Path | None = None) -> None:
    """Write a history log file."""
    path = get_history_file(iteration, root)
    write_file(path, content)


def read_prompt_md(root: Path | None = None) -> str | None:
    """Read PROMPT.md if it exists."""
    if root is None:
        root = Path.cwd()
    prompt_path = root / "PROMPT.md"
    if not prompt_path.exists():
        return None
    content = prompt_path.read_text(encoding="utf-8").strip()
    return content if content else None

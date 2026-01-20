"""Run state tracking for live Ralph inspection."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from ralph.core.state import get_ralph_dir

RUN_STATE_FILE = "run.json"
CURRENT_LOG_FILE = "current.log"


@dataclass(frozen=True)
class RunState:
    """State snapshot for a running Ralph loop."""

    pid: int
    started_at: str
    iteration: int
    max_iterations: int
    agent: str
    agent_started_at: str


def now_iso() -> str:
    """Return current UTC time in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def get_run_state_path(root: Path | None = None) -> Path:
    """Get the path to the run state file."""
    return get_ralph_dir(root) / RUN_STATE_FILE


def get_current_log_path(root: Path | None = None) -> Path:
    """Get the path to the live output log file."""
    return get_ralph_dir(root) / CURRENT_LOG_FILE


def write_run_state(state: RunState, root: Path | None = None) -> None:
    """Write the run state to disk."""
    path = get_run_state_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(state), indent=2), encoding="utf-8")


def read_run_state(root: Path | None = None) -> RunState | None:
    """Read the run state from disk."""
    path = get_run_state_path(root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None

    try:
        return RunState(**data)
    except TypeError:
        return None


def delete_run_state(root: Path | None = None) -> None:
    """Delete the run state file if it exists."""
    path = get_run_state_path(root)
    try:
        path.unlink()
    except FileNotFoundError:
        return


def is_pid_alive(pid: int) -> bool:
    """Check if a PID is alive (cross-platform)."""
    if pid <= 0:
        return False

    if os.name == "nt":
        # Windows: use ctypes to check if process is still running
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined,unused-ignore]
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                # STILL_ACTIVE (259) means process is running
                return exit_code.value == 259
            return False
        finally:
            kernel32.CloseHandle(handle)

    # Unix: use os.kill with signal 0
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    else:
        return True


def update_run_state(
    iteration: int,
    agent: str,
    agent_started_at: str | None = None,
    root: Path | None = None,
) -> RunState:
    """Update iteration and agent details in the run state."""
    existing = read_run_state(root)
    if existing is None:
        raise FileNotFoundError("run.json not found")
    updated = RunState(
        pid=existing.pid,
        started_at=existing.started_at,
        iteration=iteration,
        max_iterations=existing.max_iterations,
        agent=agent,
        agent_started_at=agent_started_at or now_iso(),
    )
    write_run_state(updated, root)
    return updated

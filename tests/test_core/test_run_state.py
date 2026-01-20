"""Tests for run state tracking."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from ralph.core.run_state import (
    RunState,
    delete_run_state,
    is_pid_alive,
    read_run_state,
    update_run_state,
    write_run_state,
)


def test_write_read_delete_run_state(initialized_project: Path) -> None:
    """Run state can be written, read, and deleted."""
    state = RunState(
        pid=os.getpid(),
        started_at="2025-01-19T14:30:00+00:00",
        iteration=1,
        max_iterations=20,
        agent="Codex",
        agent_started_at="2025-01-19T14:32:15+00:00",
    )

    write_run_state(state, initialized_project)
    read_state = read_run_state(initialized_project)
    assert read_state == state

    delete_run_state(initialized_project)
    assert read_run_state(initialized_project) is None


def test_is_pid_alive_current_pid() -> None:
    """Current PID should be alive."""
    assert is_pid_alive(os.getpid()) is True


def test_is_pid_alive_dead_pid() -> None:
    """A terminated process PID should be reported dead."""
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.1)"])
    process.wait()
    time.sleep(0.05)
    assert is_pid_alive(process.pid) is False


def test_update_run_state(initialized_project: Path) -> None:
    """Update run state modifies iteration and agent info."""
    state = RunState(
        pid=os.getpid(),
        started_at="2025-01-19T14:30:00+00:00",
        iteration=1,
        max_iterations=20,
        agent="Codex",
        agent_started_at="2025-01-19T14:32:15+00:00",
    )
    write_run_state(state, initialized_project)

    updated = update_run_state(2, "Claude", "2025-01-19T14:40:00+00:00", initialized_project)
    assert updated.iteration == 2
    assert updated.agent == "Claude"
    assert updated.agent_started_at == "2025-01-19T14:40:00+00:00"
    assert updated.pid == state.pid

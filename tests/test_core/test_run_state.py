"""Tests for run state tracking."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

import ralph.core.run_state as run_state_module
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


def _fake_windows_ctypes(handle: int, exit_code: int) -> SimpleNamespace:
    class DummyULong:
        def __init__(self) -> None:
            self.value = 0

    def open_process(_access: int, _inherit: bool, _pid: int) -> int:
        return handle

    def get_exit_code_process(_handle: int, exit_code_ptr: object) -> int:
        # ctypes.byref(c_ulong()) stores the original object on _obj
        exit_code_ptr._obj.value = exit_code
        return 1

    def close_handle(_handle: int) -> int:
        return 1

    fake_kernel32 = SimpleNamespace(
        OpenProcess=open_process,
        GetExitCodeProcess=get_exit_code_process,
        CloseHandle=close_handle,
    )

    return SimpleNamespace(
        windll=SimpleNamespace(kernel32=fake_kernel32),
        c_ulong=DummyULong,
        byref=lambda value: SimpleNamespace(_obj=value),
    )


def test_is_pid_alive_windows_still_active(monkeypatch: pytest.MonkeyPatch) -> None:
    """Windows branch returns True for STILL_ACTIVE exit code."""
    monkeypatch.setitem(sys.modules, "ctypes", _fake_windows_ctypes(handle=123, exit_code=259))
    monkeypatch.setattr(run_state_module.os, "name", "nt", raising=False)

    assert is_pid_alive(42) is True


def test_is_pid_alive_windows_exited_process(monkeypatch: pytest.MonkeyPatch) -> None:
    """Windows branch returns False when process has exited."""
    monkeypatch.setitem(sys.modules, "ctypes", _fake_windows_ctypes(handle=456, exit_code=1))
    monkeypatch.setattr(run_state_module.os, "name", "nt", raising=False)

    assert is_pid_alive(42) is False

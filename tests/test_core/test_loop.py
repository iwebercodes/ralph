"""Tests for loop engine."""

from __future__ import annotations

from pathlib import Path

from ralph.core.agent import AgentResult
from ralph.core.loop import (
    format_log_entry,
    handle_status,
    run_loop,
    run_test_command,
)
from ralph.core.pool import AgentPool
from ralph.core.state import Status, write_done_count, write_status


class TestRunTestCommand:
    """Tests for run_test_command function."""

    def test_successful_command(self) -> None:
        """Test running a successful command."""
        exit_code, output = run_test_command("echo hello")
        assert exit_code == 0
        assert "hello" in output

    def test_failing_command(self) -> None:
        """Test running a failing command."""
        exit_code, output = run_test_command("exit 1")
        assert exit_code == 1

    def test_command_with_stderr(self) -> None:
        """Test command that outputs to stderr."""
        exit_code, output = run_test_command("echo error >&2")
        assert "error" in output

    def test_nonexistent_command(self) -> None:
        """Test running a nonexistent command."""
        exit_code, output = run_test_command("nonexistent_command_12345")
        # Shell returns 127 on Unix, 1 on Windows for command not found
        assert exit_code in (1, 127)


class TestFormatLogEntry:
    """Tests for format_log_entry function."""

    def test_basic_log_entry(self) -> None:
        """Test formatting a basic log entry."""
        entry = format_log_entry(
            iteration=1,
            prompt="Test prompt",
            agent_output="Test output",
            agent_name="Claude",
            status=Status.CONTINUE,
            files_changed=[],
            test_result=None,
        )
        assert "RALPH ROTATION 1 [Claude]" in entry
        assert "Test prompt" in entry
        assert "Test output" in entry
        assert "CONTINUE" in entry
        assert "Files Changed: 0" in entry

    def test_log_entry_with_changes(self) -> None:
        """Test log entry with file changes."""
        entry = format_log_entry(
            iteration=2,
            prompt="Prompt",
            agent_output="Output",
            agent_name="Codex",
            status=Status.ROTATE,
            files_changed=["file1.py", "file2.py"],
            test_result=None,
        )
        assert "RALPH ROTATION 2 [Codex]" in entry
        assert "Files Changed: 2" in entry
        assert "file1.py" in entry
        assert "file2.py" in entry

    def test_log_entry_with_test_result(self) -> None:
        """Test log entry with test result."""
        entry = format_log_entry(
            iteration=3,
            prompt="Prompt",
            agent_output="Output",
            agent_name="Claude",
            status=Status.DONE,
            files_changed=[],
            test_result=(0, "All tests passed"),
        )
        assert "TEST COMMAND" in entry
        assert "Exit Code: 0" in entry
        assert "All tests passed" in entry


class TestHandleStatus:
    """Tests for handle_status function."""

    def test_stuck_exits_immediately(self, initialized_project: Path) -> None:
        """Test STUCK status exits with code 2."""
        action, exit_code, done_count = handle_status(Status.STUCK, [], 0, initialized_project)
        assert action == "exit"
        assert exit_code == 2
        assert done_count == 0

    def test_done_without_changes_increments(self, initialized_project: Path) -> None:
        """Test DONE without changes increments done_count."""
        action, exit_code, done_count = handle_status(Status.DONE, [], 0, initialized_project)
        assert action == "continue"
        assert exit_code is None
        assert done_count == 1

    def test_done_with_changes_resets(self, initialized_project: Path) -> None:
        """Test DONE with changes resets done_count."""
        write_done_count(2, initialized_project)
        action, exit_code, done_count = handle_status(
            Status.DONE, ["file.py"], 2, initialized_project
        )
        assert action == "continue"
        assert exit_code is None
        assert done_count == 0

    def test_done_three_times_exits(self, initialized_project: Path) -> None:
        """Test DONE 3 times exits successfully."""
        action, exit_code, done_count = handle_status(Status.DONE, [], 2, initialized_project)
        assert action == "exit"
        assert exit_code == 0
        assert done_count == 3

    def test_rotate_resets_done_count(self, initialized_project: Path) -> None:
        """Test ROTATE resets done_count."""
        write_done_count(1, initialized_project)
        action, exit_code, done_count = handle_status(
            Status.ROTATE, ["file.py"], 1, initialized_project
        )
        assert action == "continue"
        assert exit_code is None
        assert done_count == 0

    def test_continue_resets_done_count(self, initialized_project: Path) -> None:
        """Test CONTINUE resets done_count if it was > 0."""
        write_done_count(1, initialized_project)
        action, exit_code, done_count = handle_status(Status.CONTINUE, [], 1, initialized_project)
        assert action == "continue"
        assert exit_code is None
        assert done_count == 0

    def test_continue_with_zero_done_count(self, initialized_project: Path) -> None:
        """Test CONTINUE with zero done_count stays at zero."""
        action, exit_code, done_count = handle_status(Status.CONTINUE, [], 0, initialized_project)
        assert action == "continue"
        assert exit_code is None
        assert done_count == 0


class ExhaustingAgent:
    """Mock agent that becomes exhausted after first invocation."""

    def __init__(self, name: str = "Exhausting", root: Path | None = None):
        self._name = name
        self._root = root
        self.invoke_count = 0

    @property
    def name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        return True

    def invoke(self, prompt: str, timeout: int = 1800) -> AgentResult:
        self.invoke_count += 1
        if self._root:
            write_status(Status.CONTINUE, self._root)
        return AgentResult("Output", 0, "rate limit exceeded")

    def is_exhausted(self, result: AgentResult) -> bool:
        return result.error is not None and "rate limit" in result.error.lower()


class TestRunLoopWithExhaustion:
    """Tests for run_loop when agents become exhausted."""

    def test_all_agents_exhausted_returns_exit_code_4(self, project_with_prompt: Path) -> None:
        """Test that run_loop returns exit code 4 when all agents are exhausted."""
        agent = ExhaustingAgent(root=project_with_prompt)
        pool = AgentPool([agent])

        result = run_loop(
            max_iter=10,
            test_cmd=None,
            root=project_with_prompt,
            agent_pool=pool,
        )

        assert result.exit_code == 4
        assert "exhausted" in result.message.lower()

    def test_multiple_agents_all_exhausted(self, project_with_prompt: Path) -> None:
        """Test that all agents being exhausted triggers exit code 4."""
        agent1 = ExhaustingAgent(name="Agent1", root=project_with_prompt)
        agent2 = ExhaustingAgent(name="Agent2", root=project_with_prompt)
        pool = AgentPool([agent1, agent2])

        result = run_loop(
            max_iter=10,
            test_cmd=None,
            root=project_with_prompt,
            agent_pool=pool,
        )

        assert result.exit_code == 4

    def test_empty_pool_returns_exit_code_4(self, project_with_prompt: Path) -> None:
        """Test that an empty pool immediately returns exit code 4."""
        pool = AgentPool([])

        result = run_loop(
            max_iter=10,
            test_cmd=None,
            root=project_with_prompt,
            agent_pool=pool,
        )

        assert result.exit_code == 4
        assert "exhausted" in result.message.lower()

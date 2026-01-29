"""Tests for loop engine."""

from __future__ import annotations

from pathlib import Path

from ralph.core.agent import AgentResult
from ralph.core.loop import (
    IterationResult,
    format_log_entry,
    handle_status,
    run_loop,
    run_test_command,
)
from ralph.core.pool import AgentPool
from ralph.core.state import (
    MultiSpecState,
    SpecProgress,
    Status,
    get_handoff_path,
    get_history_file,
    write_status,
)


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

    def _state(self, done_counts: list[int]) -> MultiSpecState:
        specs = [
            SpecProgress(path=f"spec-{idx}.spec.md", done_count=done_count)
            for idx, done_count in enumerate(done_counts)
        ]
        return MultiSpecState(
            version=1,
            iteration=0,
            status=Status.CONTINUE,
            current_index=0,
            specs=specs,
        )

    def test_stuck_exits_immediately(self, initialized_project: Path) -> None:
        """Test STUCK status exits with code 2."""
        state = self._state([0])
        action, exit_code, _, done_count = handle_status(state, 0, Status.STUCK, [])
        assert action == "exit"
        assert exit_code == 2
        assert done_count == 0

    def test_done_without_changes_increments(self, initialized_project: Path) -> None:
        """Test DONE without changes increments done_count."""
        state = self._state([0])
        action, exit_code, _, done_count = handle_status(state, 0, Status.DONE, [])
        assert action == "continue"
        assert exit_code is None
        assert done_count == 1

    def test_done_with_changes_resets(self, initialized_project: Path) -> None:
        """Test DONE with changes resets done_count."""
        state = self._state([2, 1])
        action, exit_code, new_state, done_count = handle_status(state, 0, Status.DONE, ["file.py"])
        assert action == "continue"
        assert exit_code is None
        assert done_count == 0
        assert all(spec.done_count == 0 for spec in new_state.specs)

    def test_done_three_times_exits(self, initialized_project: Path) -> None:
        """Test DONE 3 times exits successfully."""
        state = self._state([2, 3])
        action, exit_code, _, done_count = handle_status(state, 0, Status.DONE, [])
        assert action == "exit"
        assert exit_code == 0
        assert done_count == 3

    def test_rotate_resets_done_count(self, initialized_project: Path) -> None:
        """Test ROTATE resets done_count."""
        state = self._state([1])
        action, exit_code, _, done_count = handle_status(state, 0, Status.ROTATE, ["file.py"])
        assert action == "continue"
        assert exit_code is None
        assert done_count == 0

    def test_continue_resets_done_count(self, initialized_project: Path) -> None:
        """Test CONTINUE resets done_count if it was > 0."""
        state = self._state([1])
        action, exit_code, _, done_count = handle_status(state, 0, Status.CONTINUE, [])
        assert action == "continue"
        assert exit_code is None
        assert done_count == 0

    def test_continue_with_zero_done_count(self, initialized_project: Path) -> None:
        """Test CONTINUE with zero done_count stays at zero."""
        state = self._state([0])
        action, exit_code, _, done_count = handle_status(state, 0, Status.CONTINUE, [])
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

    def invoke(
        self,
        prompt: str,
        timeout: int = 1800,
        output_file: Path | None = None,
        crash_patterns: list[str] | None = None,
    ) -> AgentResult:
        self.invoke_count += 1
        if self._root:
            write_status(Status.CONTINUE, self._root)
        return AgentResult("Output", 0, "rate limit exceeded")

    def is_exhausted(self, result: AgentResult) -> bool:
        return result.error is not None and "rate limit" in result.error.lower()

    def exhaustion_reason(self, result: AgentResult) -> str | None:
        if result.error and "rate limit" in result.error.lower():
            return "rate limit"
        return None


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

    def test_agent_removal_reported_in_callback(self, project_with_prompt: Path) -> None:
        """Test that agent removal is reported via on_iteration_end callback."""
        agent = ExhaustingAgent(name="TestAgent", root=project_with_prompt)
        pool = AgentPool([agent])
        captured_removals: list[tuple[tuple[str, str], ...]] = []

        def on_iteration_end(
            iteration: int,
            result: IterationResult,
            done_count: int,
            agent_name: str,
            spec_path: str,
        ) -> None:
            captured_removals.append(result.agent_removals)

        run_loop(
            max_iter=10,
            test_cmd=None,
            root=project_with_prompt,
            agent_pool=pool,
            on_iteration_end=on_iteration_end,
        )

        # Should have one iteration with one removal
        assert len(captured_removals) == 1
        assert captured_removals[0] == (("TestAgent", "rate limit"),)

    def test_multiple_agents_each_removal_reported(self, project_with_prompt: Path) -> None:
        """Test that each agent removal is reported in its own iteration."""
        agent1 = ExhaustingAgent(name="Agent1", root=project_with_prompt)
        agent2 = ExhaustingAgent(name="Agent2", root=project_with_prompt)
        pool = AgentPool([agent1, agent2])
        captured_removals: list[tuple[tuple[str, str], ...]] = []

        def on_iteration_end(
            iteration: int,
            result: IterationResult,
            done_count: int,
            agent_name: str,
            spec_path: str,
        ) -> None:
            captured_removals.append(result.agent_removals)

        run_loop(
            max_iter=10,
            test_cmd=None,
            root=project_with_prompt,
            agent_pool=pool,
            on_iteration_end=on_iteration_end,
        )

        # Should have two iterations, each with one removal
        assert len(captured_removals) == 2
        # Each iteration should report exactly one removal
        removal_names = {r[0][0] for r in captured_removals if r}
        assert removal_names == {"Agent1", "Agent2"}

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


class CrashThenOkAgent:
    """Mock agent that crashes once and then returns output."""

    def __init__(self, root: Path):
        self._root = root
        self._calls = 0

    @property
    def name(self) -> str:
        return "Crashy"

    def is_available(self) -> bool:
        return True

    def invoke(
        self,
        prompt: str,
        timeout: int = 1800,
        output_file: Path | None = None,
        crash_patterns: list[str] | None = None,
    ) -> AgentResult:
        self._calls += 1
        if self._calls == 1:
            return AgentResult("", 1, "ECONNRESET")
        return AgentResult("ok", 0, None)

    def is_exhausted(self, result: AgentResult) -> bool:
        return False


class ErrorPatternAgent:
    """Mock agent that returns output but reports an error pattern."""

    @property
    def name(self) -> str:
        return "Pattern"

    def is_available(self) -> bool:
        return True

    def invoke(
        self,
        prompt: str,
        timeout: int = 1800,
        output_file: Path | None = None,
        crash_patterns: list[str] | None = None,
    ) -> AgentResult:
        return AgentResult("ok", 0, "No messages returned")

    def is_exhausted(self, result: AgentResult) -> bool:
        return False


class SuccessAgent:
    """Mock agent that exits cleanly without writing status."""

    @property
    def name(self) -> str:
        return "Success"

    def is_available(self) -> bool:
        return True

    def invoke(
        self,
        prompt: str,
        timeout: int = 1800,
        output_file: Path | None = None,
        crash_patterns: list[str] | None = None,
    ) -> AgentResult:
        return AgentResult("ok", 0, None)

    def is_exhausted(self, result: AgentResult) -> bool:
        return False


class TestCrashHandling:
    """Tests for crash detection and handling."""

    def test_crash_triggers_rotate_and_logs(self, project_with_prompt: Path) -> None:
        """Test crash detection writes handoff/history and continues."""
        agent = CrashThenOkAgent(project_with_prompt)
        pool = AgentPool([agent])
        statuses: list[Status] = []

        def on_iteration_end(
            iteration: int,
            result: IterationResult,
            done_count: int,
            agent_name: str,
            spec_path: str,
        ) -> None:
            statuses.append(result.status)

        result = run_loop(
            max_iter=2,
            test_cmd=None,
            root=project_with_prompt,
            agent_pool=pool,
            on_iteration_end=on_iteration_end,
        )

        assert result.iterations_run == 2
        assert statuses[0] == Status.ROTATE
        handoff_path = get_handoff_path("PROMPT.md", project_with_prompt)
        assert handoff_path.exists()
        assert "Previous rotation crashed" in handoff_path.read_text(encoding="utf-8")

        history_path = get_history_file(1, project_with_prompt, "PROMPT.md")
        assert "CRASH DETECTED" in history_path.read_text(encoding="utf-8")

    def test_error_pattern_triggers_crash(self, project_with_prompt: Path) -> None:
        """Test stderr error pattern triggers crash handling."""
        agent = ErrorPatternAgent()
        pool = AgentPool([agent])
        statuses: list[Status] = []

        def on_iteration_end(
            iteration: int,
            result: IterationResult,
            done_count: int,
            agent_name: str,
            spec_path: str,
        ) -> None:
            statuses.append(result.status)

        run_loop(
            max_iter=1,
            test_cmd=None,
            root=project_with_prompt,
            agent_pool=pool,
            on_iteration_end=on_iteration_end,
        )

        assert statuses == [Status.ROTATE]

    def test_success_exit_does_not_mark_crash(self, project_with_prompt: Path) -> None:
        """Test clean success does not append crash notes."""
        agent = SuccessAgent()
        pool = AgentPool([agent])

        run_loop(
            max_iter=1,
            test_cmd=None,
            root=project_with_prompt,
            agent_pool=pool,
        )

        handoff_path = get_handoff_path("PROMPT.md", project_with_prompt)
        assert not handoff_path.exists()

    def test_crashed_agent_stays_in_pool(self, project_with_prompt: Path) -> None:
        """Test that crashed agents remain in pool (vs exhausted agents which are removed)."""
        agent = CrashThenOkAgent(project_with_prompt)
        pool = AgentPool([agent])

        # Before loop, pool has the agent
        assert pool.available_agents == ["Crashy"]

        run_loop(
            max_iter=2,
            test_cmd=None,
            root=project_with_prompt,
            agent_pool=pool,
        )

        # After crash + recovery, agent should still be in pool
        assert pool.available_agents == ["Crashy"]

    def test_exhausted_agent_removed_from_pool_but_crashed_stays(
        self, project_with_prompt: Path
    ) -> None:
        """Test exhaustion removes agent from pool but crash does not."""
        exhausting = ExhaustingAgent(name="Exhauster", root=project_with_prompt)
        crashing = CrashThenOkAgent(project_with_prompt)
        pool = AgentPool([exhausting, crashing])

        # Both agents start in pool
        assert set(pool.available_agents) == {"Exhauster", "Crashy"}

        run_loop(
            max_iter=5,
            test_cmd=None,
            root=project_with_prompt,
            agent_pool=pool,
        )

        # Exhausted agent should be removed, but crashed agent should remain
        assert pool.available_agents == ["Crashy"]

"""Tests for the Ralph loop state machine - specifically testing for the stale status file bug.

This test module verifies that the status file (.ralph/status) is properly reset
between iterations. The core behavior tested is in loop.py:run_iteration():
1. Status file is reset to IDLE before invoking the agent
2. agent.invoke(prompt) is called
3. read_status(root) is called to get the agent's signal
4. If the agent doesn't write a new status, Ralph reads IDLE (the reset value)

These tests verify the fix for the stale status file bug.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ralph.core.agent import AgentResult
from ralph.core.loop import run_iteration, run_loop
from ralph.core.pool import AgentPool
from ralph.core.state import (
    Status,
    read_status,
    write_done_count,
    write_status,
)


class MockAgent:
    """Mock agent for testing."""

    def __init__(
        self,
        name: str = "MockAgent",
        statuses: list[Status | None] | None = None,
        changes: list[list[str]] | None = None,
        root: Path | None = None,
    ):
        self._name = name
        self.invoke_count = 0
        self._statuses = statuses or []  # Status to write per call, or None to not write
        self._changes = changes or []  # Files to create per call
        self._root = root

    @property
    def name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        return True

    def invoke(self, prompt: str, timeout: int = 1800) -> AgentResult:
        idx = self.invoke_count
        self.invoke_count += 1

        # Write status if specified
        if idx < len(self._statuses) and self._statuses[idx] is not None:
            write_status(self._statuses[idx], self._root)

        # Create file changes if specified
        if idx < len(self._changes):
            for path_str in self._changes[idx]:
                path = Path(path_str) if self._root is None else self._root / path_str
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"modified by call {idx + 1}")

        return AgentResult(f"Output for call {idx + 1}", 0, None)

    def is_exhausted(self, result: AgentResult) -> bool:
        return False


class TestStaleStatusBug:
    """Tests that verify the status file is properly reset between iterations."""

    def test_stale_rotate_status_persists_across_iterations(
        self, project_with_prompt: Path
    ) -> None:
        """Test that a stale ROTATE status does NOT persist.

        Scenario:
        1. Set status to ROTATE (simulating previous iteration left this value)
        2. Run an iteration where agent does NOT write to status file
        3. Status should be IDLE (the reset value), not ROTATE
        """
        root = project_with_prompt

        # Pre-condition: status file contains ROTATE from "previous iteration"
        write_status(Status.ROTATE, root)

        # Create a mock agent that does NOT write to the status file
        agent = MockAgent(statuses=[None], root=root)

        result = run_iteration(
            iteration=1,
            max_iter=20,
            test_cmd=None,
            agent=agent,
            root=root,
        )

        # The status file should have been reset to IDLE before invoking agent
        assert result.status == Status.IDLE, (
            f"Expected IDLE (reset value), but got {result.status.value}. "
            "The status file should be reset before invoking agent."
        )

    def test_stale_continue_status_persists_when_claude_silent(
        self, project_with_prompt: Path
    ) -> None:
        """Test that stale CONTINUE is replaced with IDLE when agent doesn't write status."""
        root = project_with_prompt

        # Pre-condition: status file has CONTINUE from previous iteration
        write_status(Status.CONTINUE, root)

        # Create a mock agent that does NOT write to the status file
        agent = MockAgent(statuses=[None], root=root)

        run_iteration(
            iteration=1,
            max_iter=20,
            test_cmd=None,
            agent=agent,
            root=root,
        )

        # Read what's actually in the status file after the iteration
        actual_status = read_status(root)

        # The status file should have been reset before agent ran
        assert actual_status == Status.IDLE, (
            f"Expected IDLE (reset value), but got {actual_status.value}. "
            "The status file must be reset at the start of each iteration."
        )

    def test_stale_done_causes_false_verification_increment(
        self, project_with_prompt: Path
    ) -> None:
        """Test that stale DONE status is properly handled.

        Scenario:
        1. Set status to DONE, done_count to 2 (simulating near-completion)
        2. Run iteration where agent does NOT write to status file
        3. Status should be IDLE, not DONE
        """
        root = project_with_prompt

        # Pre-condition: status file has DONE, done_count is 2
        write_status(Status.DONE, root)
        write_done_count(2, root)

        # Create a mock agent that does NOT write to the status file
        agent = MockAgent(statuses=[None], root=root)

        result = run_iteration(
            iteration=1,
            max_iter=20,
            test_cmd=None,
            agent=agent,
            root=root,
        )

        # Check what status Ralph saw
        assert result.status == Status.IDLE, (
            f"Expected IDLE (reset value), but got {result.status.value}. "
            "If agent didn't write DONE, Ralph should see IDLE."
        )

    def test_status_isolation_across_multiple_iterations(self, project_with_prompt: Path) -> None:
        """Test that status values from one iteration don't leak to the next.

        Scenario:
        1. Iteration 1: Agent writes ROTATE
        2. Iteration 2: Agent writes nothing
        3. Iteration 2 should see IDLE, not ROTATE
        """
        root = project_with_prompt

        # Agent writes ROTATE on first call, nothing on second
        agent = MockAgent(
            statuses=[Status.ROTATE, None],
            changes=[["file1.txt"], []],
            root=root,
        )

        # Run first iteration
        result1 = run_iteration(iteration=1, max_iter=20, test_cmd=None, agent=agent, root=root)

        # Run second iteration (agent doesn't write status)
        result2 = run_iteration(iteration=2, max_iter=20, test_cmd=None, agent=agent, root=root)

        # Iteration 1 should see ROTATE (agent wrote it)
        assert result1.status == Status.ROTATE, "Iteration 1 should see ROTATE"

        # Iteration 2 should see IDLE (status was reset, agent didn't write)
        assert result2.status == Status.IDLE, (
            f"Expected IDLE (reset value), but iteration 2 saw {result2.status.value}. "
            "Each iteration should start with a clean status."
        )

    def test_status_file_should_be_reset_before_claude_runs(
        self, project_with_prompt: Path
    ) -> None:
        """Test that the status file is in a neutral state before agent runs."""
        root = project_with_prompt

        # Pre-condition: Set status to STUCK (a distinctive value)
        write_status(Status.STUCK, root)

        status_before_agent: Status | None = None

        class StatusCheckingAgent:
            """Agent that checks status before doing anything."""

            @property
            def name(self) -> str:
                return "StatusChecker"

            def is_available(self) -> bool:
                return True

            def invoke(self, prompt: str, timeout: int = 1800) -> AgentResult:
                nonlocal status_before_agent
                status_before_agent = read_status(root)
                return AgentResult("Mock output", 0, None)

            def is_exhausted(self, result: AgentResult) -> bool:
                return False

        agent = StatusCheckingAgent()
        run_iteration(iteration=1, max_iter=20, test_cmd=None, agent=agent, root=root)

        # The status file should NOT contain STUCK when agent runs
        # (It should have been reset to IDLE)
        assert status_before_agent == Status.IDLE, (
            f"Expected IDLE before agent runs, but found {status_before_agent.value}. "
            "Status file was not reset before invoking agent."
        )

    def test_multiple_iterations_each_status_should_be_fresh(
        self, project_with_prompt: Path
    ) -> None:
        """Test that each iteration sees only the status written by that iteration's agent.

        This test runs 4 iterations with a pattern:
        - Iteration 1: Agent writes CONTINUE
        - Iteration 2: Agent writes nothing (should see IDLE)
        - Iteration 3: Agent writes DONE
        - Iteration 4: Agent writes nothing (should see IDLE)
        """
        root = project_with_prompt

        agent = MockAgent(
            statuses=[Status.CONTINUE, None, Status.DONE, None],
            changes=[["file1.txt"], ["file2.txt"], ["file3.txt"], ["file4.txt"]],
            root=root,
        )

        iteration_statuses: list[Status] = []
        for i in range(1, 5):
            result = run_iteration(iteration=i, max_iter=20, test_cmd=None, agent=agent, root=root)
            iteration_statuses.append(result.status)

        # Iteration 1: Agent wrote CONTINUE, should see CONTINUE
        assert iteration_statuses[0] == Status.CONTINUE

        # Iteration 2: Agent wrote nothing, should see IDLE
        assert iteration_statuses[1] == Status.IDLE, (
            f"Expected IDLE, but iteration 2 saw {iteration_statuses[1].value}"
        )

        # Iteration 3: Agent wrote DONE, should see DONE
        assert iteration_statuses[2] == Status.DONE

        # Iteration 4: Agent wrote nothing, should see IDLE
        assert iteration_statuses[3] == Status.IDLE, (
            f"Expected IDLE, but iteration 4 saw {iteration_statuses[3].value}"
        )


class TestStaleStatusInFullLoop:
    """Tests for status handling in the context of the full run_loop function."""

    def test_run_loop_with_stale_done_causes_premature_exit(
        self, project_with_prompt: Path
    ) -> None:
        """Test that stale DONE status does NOT cause premature loop exit.

        Scenario:
        1. Pre-set status to DONE
        2. Run loop where agent never writes status (but makes changes on first iteration)
        3. Loop should NOT exit with success (agent never signaled DONE)
        """
        root = project_with_prompt

        # Pre-condition: stale DONE status
        write_status(Status.DONE, root)

        agent = MockAgent(
            statuses=[None, None, None, None, None],  # Never write status
            changes=[["file.txt"], [], [], [], []],  # Only first iteration makes changes
            root=root,
        )
        pool = AgentPool([agent])

        result = run_loop(
            max_iter=10,
            test_cmd=None,
            root=root,
            agent_pool=pool,
        )

        # With the fix, the loop should NOT exit with "Goal achieved!"
        # because the status is reset to IDLE and agent never writes DONE
        assert not (result.exit_code == 0 and result.message == "Goal achieved!"), (
            f"Loop incorrectly exited with 'Goal achieved!' after {result.iterations_run} "
            "iterations, but agent never actually signaled DONE."
        )

    def test_run_loop_stale_rotate_causes_endless_rotation(self, project_with_prompt: Path) -> None:
        """Test that stale ROTATE status does NOT persist when agent doesn't write status."""
        root = project_with_prompt

        # Pre-condition: stale ROTATE status
        write_status(Status.ROTATE, root)

        agent = MockAgent(
            statuses=[None, None, None, None, None],  # Never write status
            changes=[
                [f"file_{i}.txt"] for i in range(5)
            ],  # Make changes to differentiate iterations
            root=root,
        )
        pool = AgentPool([agent])

        observed_statuses: list[Status] = []

        def on_iteration_end(iteration: int, result: Any, done_count: int, agent_name: str) -> None:
            observed_statuses.append(result.status)

        run_loop(
            max_iter=5,
            test_cmd=None,
            root=root,
            agent_pool=pool,
            on_iteration_end=on_iteration_end,
        )

        # With the fix, no iteration should see ROTATE (agent never wrote it)
        # All should see IDLE
        for i, status in enumerate(observed_statuses):
            assert status == Status.IDLE, (
                f"Iteration {i + 1} saw {status.value}, expected IDLE. "
                "Status file should be reset before each iteration."
            )


class TestExpectedBehaviorDocumentation:
    """These tests document the correct behavior."""

    def test_default_status_when_claude_silent_should_be_defined(
        self, project_with_prompt: Path
    ) -> None:
        """Document that the default when agent doesn't write status is IDLE.

        When the agent doesn't write to the status file, the system reads IDLE
        because the status file is reset to IDLE before each iteration.
        """
        root = project_with_prompt

        # Start with a clearly wrong value
        write_status(Status.STUCK, root)

        agent = MockAgent(
            statuses=[None],  # Don't write status
            changes=[["file.txt"]],  # Make a change to avoid STUCK exit behavior
            root=root,
        )

        result = run_iteration(iteration=1, max_iter=20, test_cmd=None, agent=agent, root=root)

        # The system should see IDLE when agent didn't signal anything
        assert result.status == Status.IDLE, (
            f"Expected IDLE (reset value), but got {result.status.value}. "
            "When agent doesn't write a status, the result should be IDLE."
        )

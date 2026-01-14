"""Tests for the Ralph loop state machine - specifically testing for the stale status file bug.

This test module documents and exposes a bug where the status file (.ralph/status) is
never reset between iterations. When Claude doesn't write a new status, Ralph reads
the stale value from the previous iteration.

The core issue is in loop.py:run_iteration():
1. invoke_claude(prompt) is called
2. read_status(root) is called to get Claude's signal
3. But the status file is never reset BEFORE invoking Claude
4. So if Claude doesn't write to the status file, Ralph reads whatever was there before

These tests are designed to FAIL against the current implementation to prove the bug exists.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from ralph.core.loop import run_iteration, run_loop
from ralph.core.state import (
    Status,
    read_status,
    write_done_count,
    write_status,
)


class MockClaudeResult:
    """Mock result from invoke_claude."""

    def __init__(self, output: str = "Mock output", exit_code: int = 0, error: str | None = None):
        self.output = output
        self.exit_code = exit_code
        self.error = error


def create_mock_claude_that_writes_status(status: Status | None, output: str = "Mock output"):
    """Create a mock invoke_claude that optionally writes a status.

    Args:
        status: The status to write, or None to simulate Claude not writing any status.
        output: The output string to return.

    Returns:
        A mock function suitable for patching invoke_claude.
    """

    def mock_invoke_claude(prompt: str) -> MockClaudeResult:
        if status is not None:
            # Simulate Claude writing to the status file
            write_status(status)
        # If status is None, we simulate Claude NOT writing to the status file at all
        return MockClaudeResult(output=output)

    return mock_invoke_claude


def create_mock_claude_sequence(responses: list[dict[str, Any]]):
    """Create a mock that returns different responses for each call.

    Each response dict can have:
        - "status": Status to write (or None to not write)
        - "output": Output string
        - "changes": List of file paths to create/modify (relative to cwd)
    """
    call_count = 0

    def mock_invoke_claude(prompt: str) -> MockClaudeResult:
        nonlocal call_count
        if call_count < len(responses):
            response = responses[call_count]
            status = response.get("status")
            output = response.get("output", "Mock output")

            if status is not None:
                write_status(status)

            # Create any file changes
            for path_str in response.get("changes", []):
                path = Path(path_str)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"modified by call {call_count + 1}")

            call_count += 1
            return MockClaudeResult(output=output)
        return MockClaudeResult(output="Exhausted responses")

    return mock_invoke_claude


class TestStaleStatusBug:
    """Tests that demonstrate the stale status file bug.

    These tests SHOULD FAIL against the current implementation because the bug causes
    Ralph to read stale status values when Claude doesn't write a new status.
    """

    def test_stale_rotate_status_persists_across_iterations(
        self, project_with_prompt: Path
    ) -> None:
        """Test that a stale ROTATE status incorrectly persists.

        Scenario:
        1. Set status to ROTATE (simulating previous iteration left this value)
        2. Run an iteration where Claude does NOT write to status file
        3. Expected (correct behavior): Status should NOT be ROTATE
        4. Actual (bug): Ralph reads the stale ROTATE

        This test should FAIL because Ralph currently reads the stale ROTATE.
        """
        root = project_with_prompt

        # Pre-condition: status file contains ROTATE from "previous iteration"
        write_status(Status.ROTATE, root)

        # Create a mock Claude that does NOT write to the status file
        mock_claude = create_mock_claude_that_writes_status(status=None)

        with patch("ralph.core.loop.invoke_claude", mock_claude):
            result = run_iteration(
                iteration=1,
                max_iter=20,
                test_cmd=None,
                root=root,
            )

        # The bug: Ralph reads the stale ROTATE because it was never cleared
        # This assertion documents correct behavior, so it should FAIL with current code
        assert result.status != Status.ROTATE, (
            "BUG CONFIRMED: Ralph read stale ROTATE status from previous iteration. "
            "The status file should be reset before invoking Claude."
        )

    def test_stale_continue_status_persists_when_claude_silent(
        self, project_with_prompt: Path
    ) -> None:
        """Test that a stale CONTINUE status persists when Claude doesn't write status.

        This documents that the status file is NOT reset to a neutral state before
        Claude runs.

        This test should FAIL because Ralph currently reads the stale CONTINUE.
        """
        root = project_with_prompt

        # Pre-condition: status file has CONTINUE from previous iteration
        write_status(Status.CONTINUE, root)

        # Create a mock Claude that does NOT write to the status file
        mock_claude = create_mock_claude_that_writes_status(status=None)

        with patch("ralph.core.loop.invoke_claude", mock_claude):
            run_iteration(
                iteration=1,
                max_iter=20,
                test_cmd=None,
                root=root,
            )

        # Read what's actually in the status file after the iteration
        actual_status = read_status(root)

        # The status file should have been reset before Claude ran
        # If Claude didn't write anything, we should NOT see the old CONTINUE
        # This assertion documents correct behavior, so it should FAIL with current code
        assert actual_status != Status.CONTINUE, (
            "BUG CONFIRMED: Status file was not reset before Claude ran. "
            "Expected neutral/reset state, but found stale CONTINUE. "
            "The status file must be reset at the start of each iteration."
        )

    def test_stale_done_causes_false_verification_increment(
        self, project_with_prompt: Path
    ) -> None:
        """Test that stale DONE status incorrectly increments done_count.

        Scenario:
        1. Set status to DONE, done_count to 2 (simulating near-completion)
        2. Run iteration where Claude does NOT write to status file
        3. Expected: done_count should NOT increment (Claude didn't signal DONE)
        4. Bug: done_count increments to 3 because Ralph reads stale DONE

        This is particularly dangerous because it could cause Ralph to exit
        prematurely thinking the goal is achieved.

        This test should FAIL because the bug causes the false increment.
        """
        root = project_with_prompt

        # Pre-condition: status file has DONE, done_count is 2
        write_status(Status.DONE, root)
        write_done_count(2, root)

        # Create a mock Claude that does NOT write to the status file
        # and makes no file changes
        mock_claude = create_mock_claude_that_writes_status(status=None)

        with patch("ralph.core.loop.invoke_claude", mock_claude):
            result = run_iteration(
                iteration=1,
                max_iter=20,
                test_cmd=None,
                root=root,
            )

        # Check what status Ralph saw
        assert result.status != Status.DONE, (
            "BUG CONFIRMED: Ralph read stale DONE status. "
            "If Claude didn't write DONE, Ralph should not see DONE. "
            "This could cause premature exit if done_count reaches 3."
        )

    def test_status_isolation_across_multiple_iterations(
        self, project_with_prompt: Path
    ) -> None:
        """Test that status values from one iteration don't leak to the next.

        Scenario:
        1. Iteration 1: Claude writes ROTATE
        2. Iteration 2: Claude writes nothing
        3. Expected: Iteration 2 should NOT see ROTATE
        4. Bug: Iteration 2 reads stale ROTATE from iteration 1

        This test should FAIL because the status file persists between iterations.
        """
        root = project_with_prompt

        # Track calls to mock
        call_count = 0

        def mock_invoke_claude(prompt: str) -> MockClaudeResult:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First iteration: Claude writes ROTATE and makes changes
                write_status(Status.ROTATE, root)
                Path(root / "file1.txt").write_text("created in iteration 1")
            # Second iteration: Claude does NOT write to status file
            # (Simulates Claude forgetting or failing to signal)
            return MockClaudeResult(output=f"Output for call {call_count}")

        captured_results: list[Status] = []

        with patch("ralph.core.loop.invoke_claude", mock_invoke_claude):
            # Run first iteration
            result1 = run_iteration(iteration=1, max_iter=20, test_cmd=None, root=root)
            captured_results.append(result1.status)

            # Run second iteration (Claude doesn't write status)
            result2 = run_iteration(iteration=2, max_iter=20, test_cmd=None, root=root)
            captured_results.append(result2.status)

        # Iteration 1 should see ROTATE (Claude wrote it)
        assert captured_results[0] == Status.ROTATE, "Iteration 1 should see ROTATE"

        # Iteration 2 should NOT see ROTATE (Claude didn't write it)
        # This assertion documents correct behavior, so it should FAIL with current code
        assert captured_results[1] != Status.ROTATE, (
            "BUG CONFIRMED: Status from iteration 1 leaked to iteration 2. "
            f"Iteration 2 saw {captured_results[1].value} but Claude didn't write any status. "
            "Each iteration should start with a clean/neutral status."
        )

    def test_status_file_should_be_reset_before_claude_runs(
        self, project_with_prompt: Path
    ) -> None:
        """Test that the status file is in a neutral state before Claude runs.

        The contract should be:
        1. Before each iteration, status file is reset to neutral (IDLE or similar)
        2. Claude runs and MAY write a new status
        3. After Claude runs, status file contains Claude's signal
           (or neutral if Claude didn't write)

        This test verifies that pre-existing status values don't persist.

        This test should FAIL because Ralph never resets the status file.
        """
        root = project_with_prompt

        # Pre-condition: Set status to STUCK (a distinctive value)
        write_status(Status.STUCK, root)

        status_before_claude: Status | None = None
        status_after_claude: Status | None = None

        def mock_invoke_claude_that_checks_status(prompt: str) -> MockClaudeResult:
            nonlocal status_before_claude, status_after_claude
            # Check what status file contains BEFORE Claude does anything
            status_before_claude = read_status(root)
            # Claude doesn't write anything
            status_after_claude = read_status(root)
            return MockClaudeResult(output="Mock output")

        with patch("ralph.core.loop.invoke_claude", mock_invoke_claude_that_checks_status):
            run_iteration(iteration=1, max_iter=20, test_cmd=None, root=root)

        # The status file should NOT contain STUCK when Claude runs
        # (It should have been reset to a neutral value)
        assert status_before_claude != Status.STUCK, (
            "BUG CONFIRMED: Status file was not reset before invoking Claude. "
            "Found stale STUCK status. Claude could read this and become confused."
        )

    def test_multiple_iterations_each_status_should_be_fresh(
        self, project_with_prompt: Path
    ) -> None:
        """Test that each iteration sees only the status written by that iteration's Claude.

        This test runs 4 iterations with a pattern:
        - Iteration 1: Claude writes CONTINUE
        - Iteration 2: Claude writes nothing (should NOT see CONTINUE)
        - Iteration 3: Claude writes DONE
        - Iteration 4: Claude writes nothing (should NOT see DONE)

        This test should FAIL because iterations 2 and 4 will see stale status.
        """
        root = project_with_prompt

        call_count = 0
        iteration_statuses: list[Status] = []

        def mock_invoke_claude(prompt: str) -> MockClaudeResult:
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                write_status(Status.CONTINUE, root)
                Path(root / "file1.txt").write_text("created")
            elif call_count == 2:
                # Don't write status - simulates Claude forgetting
                Path(root / "file2.txt").write_text("created")
            elif call_count == 3:
                write_status(Status.DONE, root)
                Path(root / "file3.txt").write_text("created")
            elif call_count == 4:
                # Don't write status - simulates Claude forgetting
                Path(root / "file4.txt").write_text("created")

            return MockClaudeResult(output=f"Output {call_count}")

        with patch("ralph.core.loop.invoke_claude", mock_invoke_claude):
            for i in range(1, 5):
                result = run_iteration(iteration=i, max_iter=20, test_cmd=None, root=root)
                iteration_statuses.append(result.status)

        # Iteration 1: Claude wrote CONTINUE, should see CONTINUE - OK
        assert iteration_statuses[0] == Status.CONTINUE

        # Iteration 2: Claude wrote nothing, should NOT see CONTINUE
        # This should FAIL with current buggy code
        assert iteration_statuses[1] != Status.CONTINUE, (
            f"BUG CONFIRMED: Iteration 2 saw stale {iteration_statuses[1].value} "
            "from iteration 1, but Claude didn't write any status."
        )

        # Iteration 3: Claude wrote DONE, should see DONE - OK
        assert iteration_statuses[2] == Status.DONE

        # Iteration 4: Claude wrote nothing, should NOT see DONE
        # This should FAIL with current buggy code
        assert iteration_statuses[3] != Status.DONE, (
            f"BUG CONFIRMED: Iteration 4 saw stale {iteration_statuses[3].value} "
            "from iteration 3, but Claude didn't write any status."
        )


class TestStaleStatusInFullLoop:
    """Tests for the stale status bug in the context of the full run_loop function."""

    def test_run_loop_with_stale_done_causes_premature_exit(
        self, project_with_prompt: Path
    ) -> None:
        """Test that stale DONE status can cause premature loop exit.

        This is the most dangerous manifestation of the bug: if DONE persists
        and Claude doesn't write a new status for 3 iterations without file changes,
        Ralph will exit thinking the goal is achieved.

        Scenario:
        1. Pre-set status to DONE
        2. Run loop where Claude never writes status (but makes changes on first iteration)
        3. Expected: Loop should NOT exit with success (Claude never signaled DONE)
        4. Bug: Loop may exit early thinking goal is achieved

        This test should FAIL (or show buggy behavior) with current implementation.
        """
        root = project_with_prompt

        # Pre-condition: stale DONE status
        write_status(Status.DONE, root)

        call_count = 0

        def mock_invoke_claude(prompt: str) -> MockClaudeResult:
            nonlocal call_count
            call_count += 1
            # Claude NEVER writes to the status file
            # But makes changes only on first call
            if call_count == 1:
                Path(root / "file.txt").write_text("created")
            # No file changes on subsequent calls, no status written
            return MockClaudeResult(output=f"Output {call_count}")

        with patch("ralph.core.loop.invoke_claude", mock_invoke_claude):
            result = run_loop(
                max_iter=10,
                test_cmd=None,
                root=root,
            )

        # If the bug is present, the loop will exit with success after ~3-4 iterations
        # because it reads stale DONE status and done_count increments
        # The correct behavior is that Claude must actually signal DONE for goal completion

        if result.exit_code == 0 and result.message == "Goal achieved!":
            pytest.fail(
                f"BUG CONFIRMED: Loop exited with 'Goal achieved!' after {result.iterations_run} "
                "iterations, but Claude never actually signaled DONE. "
                "Ralph was reading stale DONE status from before the loop started."
            )

    def test_run_loop_stale_rotate_causes_endless_rotation(
        self, project_with_prompt: Path
    ) -> None:
        """Test that stale ROTATE status persists if Claude doesn't write status.

        If ROTATE persists, the loop will continue "rotating" even though Claude
        isn't actually signaling rotation.

        This test should show that the status remains ROTATE across iterations
        when Claude doesn't write a new status.
        """
        root = project_with_prompt

        # Pre-condition: stale ROTATE status
        write_status(Status.ROTATE, root)

        observed_statuses: list[Status] = []

        def mock_invoke_claude(prompt: str) -> MockClaudeResult:
            # Claude NEVER writes to the status file
            # Make a change so we can differentiate iterations
            Path(root / f"file_{len(observed_statuses)}.txt").write_text("created")
            return MockClaudeResult(output="Mock output")

        def on_iteration_end(iteration: int, result: Any, done_count: int) -> None:
            observed_statuses.append(result.status)

        with patch("ralph.core.loop.invoke_claude", mock_invoke_claude):
            run_loop(
                max_iter=5,
                test_cmd=None,
                root=root,
                on_iteration_end=on_iteration_end,
            )

        # Every iteration should NOT see ROTATE (Claude never wrote it)
        # But due to the bug, all iterations will see the stale ROTATE
        stale_rotate_count = sum(1 for s in observed_statuses if s == Status.ROTATE)

        # If even one iteration after the first sees ROTATE, that's a bug
        # (The first iteration might see it because we set it up that way,
        # but subsequent iterations should NOT see it if the file was reset)
        if stale_rotate_count > 0:
            pytest.fail(
                f"BUG CONFIRMED: {stale_rotate_count} out of {len(observed_statuses)} "
                f"iterations saw ROTATE status, but Claude never wrote ROTATE. "
                f"Observed statuses: {[s.value for s in observed_statuses]}"
            )


class TestExpectedBehaviorDocumentation:
    """These tests document what the CORRECT behavior should be.

    They are expected to fail with the current implementation, demonstrating
    that the bug prevents the system from working correctly.
    """

    def test_default_status_when_claude_silent_should_be_defined(
        self, project_with_prompt: Path
    ) -> None:
        """Document that there should be a defined default when Claude doesn't write status.

        When Claude doesn't write to the status file, the system should have a
        well-defined default behavior. Currently, it reads whatever garbage
        was in the file before.

        Options for correct behavior:
        1. Reset to IDLE before each iteration
        2. Reset to CONTINUE before each iteration (conservative: keep going)
        3. Treat missing/unchanged status as an error

        This test documents that the current behavior (reading stale data) is wrong.
        """
        root = project_with_prompt

        # Start with a clearly wrong value
        write_status(Status.STUCK, root)

        mock_claude = create_mock_claude_that_writes_status(status=None)

        with patch("ralph.core.loop.invoke_claude", mock_claude):
            # Create a file change to avoid STUCK exit
            Path(root / "file.txt").write_text("created before iteration")

            result = run_iteration(iteration=1, max_iter=20, test_cmd=None, root=root)

        # The system should NOT see STUCK when Claude didn't signal STUCK
        assert result.status != Status.STUCK, (
            "BUG CONFIRMED: System read stale STUCK status. "
            "When Claude doesn't write a status, the result should be a defined default, "
            "not whatever happened to be in the file before."
        )

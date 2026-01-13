"""Tests for console output."""

from __future__ import annotations

import pytest

from ralph.core.state import Status
from ralph.output.console import Console


class TestConsole:
    """Tests for Console class."""

    def test_is_tty_property(self) -> None:
        """Test is_tty property."""
        console = Console(no_color=True)
        # In tests, stdout is not a TTY
        assert console.is_tty is False

    def test_error_message(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test error message output."""
        console = Console(no_color=True)
        console.error("Something went wrong")
        output = capsys.readouterr().out
        assert "Error: Something went wrong" in output

    def test_warning_message(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test warning message output."""
        console = Console(no_color=True)
        console.warning("Be careful")
        output = capsys.readouterr().out
        assert "Warning: Be careful" in output

    def test_info_message(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test info message output."""
        console = Console(no_color=True)
        console.info("Just FYI")
        output = capsys.readouterr().out
        assert "Just FYI" in output

    def test_success_message(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test success message output."""
        console = Console(no_color=True)
        console.success("It worked!")
        output = capsys.readouterr().out
        assert "It worked!" in output

    def test_verification_circles(self) -> None:
        """Test verification circles formatting."""
        console = Console(no_color=True)
        assert console._verification_circles(0) == "[○○○]"
        assert console._verification_circles(1) == "[●○○]"
        assert console._verification_circles(2) == "[●●○]"
        assert console._verification_circles(3) == "[●●●]"

    def test_iteration_info_non_tty(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test iteration info for non-TTY output."""
        console = Console(no_color=True)
        console.iteration_info(5, 20, 0)
        output = capsys.readouterr().out
        assert "[ralph]" in output
        assert "5/20" in output
        assert "───" in output  # Visual separator

    def test_iteration_info_non_tty_review(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test iteration info in review mode for non-TTY."""
        console = Console(no_color=True)
        console.iteration_info(5, 20, 1)
        output = capsys.readouterr().out
        assert "[REVIEW]" in output

    def test_rotation_complete_non_tty(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test rotation complete for non-TTY output."""
        console = Console(no_color=True)
        console.rotation_complete(Status.ROTATE, ["file1.py", "file2.py"], 0)
        output = capsys.readouterr().out
        assert "[ralph]" in output
        assert "ROTATE" in output
        assert "2 files" in output

    def test_rotation_complete_no_changes(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test rotation complete with no changes."""
        console = Console(no_color=True)
        console.rotation_complete(Status.DONE, [], 1)
        output = capsys.readouterr().out
        assert "no changes" in output
        assert "1/3" in output

    def test_test_result_non_tty(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test test result for non-TTY output."""
        console = Console(no_color=True)
        console.test_result("pytest", 0, passed=True)
        output = capsys.readouterr().out
        assert "[ralph]" in output
        assert "passed" in output

    def test_test_result_failed_non_tty(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test failed test result for non-TTY output."""
        console = Console(no_color=True)
        console.test_result("pytest", 1, passed=False)
        output = capsys.readouterr().out
        assert "FAILED" in output
        assert "exit code 1" in output

    def test_goal_achieved_non_tty(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test goal achieved for non-TTY output."""
        console = Console(no_color=True)
        console.goal_achieved(5, "2m 30s")
        output = capsys.readouterr().out
        assert "[ralph]" in output
        assert "Goal achieved" in output
        assert "5 iterations" in output
        assert "2m 30s" in output

    def test_stuck_non_tty(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test stuck message for non-TTY output."""
        console = Console(no_color=True)
        console.stuck()
        output = capsys.readouterr().out
        assert "BLOCKED" in output
        assert "handoff.md" in output

    def test_max_iterations_non_tty(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test max iterations for non-TTY output."""
        console = Console(no_color=True)
        console.max_iterations(20)
        output = capsys.readouterr().out
        assert "[ralph]" in output
        assert "Max iterations" in output
        assert "20" in output


class TestConsoleTTY:
    """Tests for Console TTY output paths."""

    def test_banner_tty(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test banner output for TTY."""
        console = Console(no_color=True)
        console._is_tty = True
        console.banner()
        output = capsys.readouterr().out
        assert "RALPH LOOP" in output
        assert "Autonomous development" in output
        assert "─" in output

    def test_working_tty(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test working message for TTY."""
        console = Console(no_color=True)
        console._is_tty = True
        console.working(done_count=0)
        output = capsys.readouterr().out
        assert "Claude working..." in output
        assert "──" in output

    def test_working_review_tty(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test working message in review mode for TTY."""
        console = Console(no_color=True)
        console._is_tty = True
        console.working(done_count=1)
        output = capsys.readouterr().out
        assert "Claude reviewing..." in output

    def test_iteration_info_tty(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test iteration info for TTY output."""
        console = Console(no_color=True)
        console._is_tty = True
        console.iteration_info(5, 20, 0)
        output = capsys.readouterr().out
        assert "Iteration:" in output
        assert "5" in output
        # Status line removed - box title shows working/reviewing state

    def test_iteration_info_tty_review(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test iteration info in review mode for TTY."""
        console = Console(no_color=True)
        console._is_tty = True
        console.iteration_info(5, 20, 1)
        output = capsys.readouterr().out
        assert "[REVIEW]" in output
        # REVIEWING status line removed - box title shows reviewing state

    def test_rotation_complete_tty_rotate(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test rotation complete with ROTATE status for TTY."""
        console = Console(no_color=True)
        console._is_tty = True
        console.rotation_complete(Status.ROTATE, ["file1.py", "file2.py"], 0)
        output = capsys.readouterr().out
        assert "Rotation complete" in output
        assert "ROTATE" in output
        assert "2 files" in output

    def test_rotation_complete_tty_done(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test rotation complete with DONE status for TTY."""
        console = Console(no_color=True)
        console._is_tty = True
        console.rotation_complete(Status.DONE, [], 2)
        output = capsys.readouterr().out
        assert "DONE" in output
        assert "Files:        no changes" in output
        assert "2/3" in output
        assert "[●●○]" in output

    def test_rotation_complete_tty_done_complete(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test rotation complete with DONE status at 3/3 for TTY."""
        console = Console(no_color=True)
        console._is_tty = True
        console.rotation_complete(Status.DONE, [], 3)
        output = capsys.readouterr().out
        assert "3/3" in output
        assert "[●●●]" in output

    def test_rotation_complete_tty_stuck(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test rotation complete with STUCK status for TTY."""
        console = Console(no_color=True)
        console._is_tty = True
        console.rotation_complete(Status.STUCK, [], 0)
        output = capsys.readouterr().out
        assert "STUCK" in output

    def test_rotation_complete_tty_continue(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test rotation complete with CONTINUE status for TTY."""
        console = Console(no_color=True)
        console._is_tty = True
        console.rotation_complete(Status.CONTINUE, ["f.py"], 0)
        output = capsys.readouterr().out
        assert "CONTINUE" in output

    def test_test_result_tty(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test test result for TTY output."""
        console = Console(no_color=True)
        console._is_tty = True
        console.test_result("pytest", 0, passed=True)
        output = capsys.readouterr().out
        assert "Tests:" in output
        assert "pytest" in output
        assert "passed" in output

    def test_test_result_failed_tty(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test failed test result for TTY output."""
        console = Console(no_color=True)
        console._is_tty = True
        console.test_result("pytest", 1, passed=False)
        output = capsys.readouterr().out
        assert "failed" in output

    def test_goal_achieved_tty(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test goal achieved for TTY output."""
        console = Console(no_color=True)
        console._is_tty = True
        console.goal_achieved(5, "2m 30s")
        output = capsys.readouterr().out
        assert "COMPLETE" in output
        assert "Goal achieved" in output
        assert "5 iterations" in output
        assert "3/3 verified" in output
        assert "2m 30s" in output
        assert "─" in output

    def test_stuck_tty(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test stuck message for TTY output."""
        console = Console(no_color=True)
        console._is_tty = True
        console.stuck()
        output = capsys.readouterr().out
        assert "BLOCKED" in output
        assert "Human input needed" in output
        assert "handoff.md" in output
        assert "Next steps:" in output
        assert "─" in output

    def test_max_iterations_tty(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test max iterations for TTY output."""
        console = Console(no_color=True)
        console._is_tty = True
        console.max_iterations(20)
        output = capsys.readouterr().out
        assert "MAX ITERATIONS" in output
        assert "20/20" in output
        assert "handoff.md" in output
        assert "ralph run" in output
        assert "ralph reset" in output
        assert "─" in output

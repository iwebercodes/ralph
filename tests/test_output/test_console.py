"""Tests for console output."""

from __future__ import annotations

import pytest

from ralph.core.state import Status
from ralph.output.console import Console, format_human_duration


class TestFormatHumanDuration:
    """Tests for format_human_duration function."""

    def test_seconds_only(self) -> None:
        """Test formatting seconds only."""
        assert format_human_duration(0) == "0s"
        assert format_human_duration(45) == "45s"
        assert format_human_duration(59) == "59s"
        assert format_human_duration(45.7) == "45s"  # Rounds down

    def test_minutes_and_seconds(self) -> None:
        """Test formatting minutes and seconds."""
        assert format_human_duration(60) == "1m 0s"
        assert format_human_duration(133) == "2m 13s"
        assert format_human_duration(599) == "9m 59s"
        assert format_human_duration(3599) == "59m 59s"

    def test_hours_minutes_seconds(self) -> None:
        """Test formatting hours, minutes and seconds."""
        assert format_human_duration(3600) == "1h 0m 0s"
        assert format_human_duration(3665) == "1h 1m 5s"
        assert format_human_duration(4430) == "1h 13m 50s"
        assert format_human_duration(7385) == "2h 3m 5s"
        assert format_human_duration(36000) == "10h 0m 0s"


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

    def test_render_history_rotation(self) -> None:
        """Single-rotation history rendering uses the expected header format."""
        console = Console(no_color=True)
        rendered = console.render_history_rotation(7, "line a\nline b")
        assert rendered.startswith("Ralph History - Rotation 7\n")
        assert "━" * 52 in rendered
        assert rendered.endswith("line a\nline b")

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

    def test_iteration_info_shows_spec_path(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test iteration info shows spec path even for single PROMPT.md."""
        console = Console(no_color=True)
        console.iteration_info(1, 20, 0, spec_path="PROMPT.md")
        output = capsys.readouterr().out
        assert "Spec: PROMPT.md" in output

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

    def test_rotation_complete_non_tty_agent_removed(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test rotation complete with agent removal for non-TTY output."""
        console = Console(no_color=True)
        console.rotation_complete(
            Status.ROTATE,
            ["file1.py"],
            0,
            agent_removals=(("Codex", "rate limit"),),
        )
        output = capsys.readouterr().out
        assert "Agent removed: Codex (rate limit)" in output

    def test_rotation_complete_non_tty_multiple_agent_removals(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test rotation complete with multiple agent removals for non-TTY output."""
        console = Console(no_color=True)
        console.rotation_complete(
            Status.ROTATE,
            [],
            0,
            agent_removals=(("Claude", "rate limit"), ("Codex", "quota exceeded")),
        )
        output = capsys.readouterr().out
        assert "Agent removed: Claude (rate limit)" in output
        assert "Agent removed: Codex (quota exceeded)" in output

    def test_rotation_complete_non_tty_codex_reset_time_reason(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test non-TTY output preserves Codex reset-time exhaustion details."""
        console = Console(no_color=True)
        console.rotation_complete(
            Status.ROTATE,
            [],
            0,
            agent_removals=(("Codex", "usage limit reached (resets in 33 minutes)"),),
        )
        output = capsys.readouterr().out
        assert "Agent removed: Codex (usage limit reached (resets in 33 minutes))" in output

    def test_rotation_complete_non_tty_with_duration(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test rotation complete with duration for non-TTY output."""
        console = Console(no_color=True)
        console.rotation_complete(Status.DONE, ["file1.py"], 1, duration=133.0)
        output = capsys.readouterr().out
        assert "Result: DONE" in output
        assert "Time: 2m 13s" in output

    def test_rotation_complete_non_tty_duration_ordering(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Time line appears after files and before removals/verification in non-TTY."""
        console = Console(no_color=True)
        console.rotation_complete(
            Status.DONE,
            ["file1.py"],
            1,
            agent_removals=(("Codex", "rate limit"),),
            duration=133.0,
        )
        output = capsys.readouterr().out
        files_idx = output.index("Result: DONE (1 file changed)")
        time_idx = output.index("Time: 2m 13s")
        agent_idx = output.index("Agent removed: Codex (rate limit)")
        verify_idx = output.index("Verification: 1/3 [●○○]")
        assert files_idx < time_idx < agent_idx < verify_idx

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
        assert "handoffs" in output

    def test_max_iterations_non_tty(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test max iterations for non-TTY output."""
        console = Console(no_color=True)
        console.max_iterations(20)
        output = capsys.readouterr().out
        assert "[ralph]" in output
        assert "Max iterations" in output
        assert "20" in output

    def test_all_agents_exhausted_non_tty(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test all agents exhausted for non-TTY output."""
        console = Console(no_color=True)
        console.all_agents_exhausted()
        output = capsys.readouterr().out
        assert "[ralph]" in output
        assert "exhausted" in output.lower()
        assert "rate limited" in output.lower()


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
        console.working(done_count=0, agent_name="Claude")
        output = capsys.readouterr().out
        assert "Claude working..." in output
        assert "──" in output

    def test_working_review_tty(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test working message in review mode for TTY."""
        console = Console(no_color=True)
        console._is_tty = True
        console.working(done_count=1, agent_name="Claude")
        output = capsys.readouterr().out
        assert "Claude reviewing..." in output

    def test_working_tty_codex(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test working message for Codex agent."""
        console = Console(no_color=True)
        console._is_tty = True
        console.working(done_count=0, agent_name="Codex")
        output = capsys.readouterr().out
        assert "Codex working..." in output

    def test_working_review_tty_codex(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test working message in review mode for Codex agent."""
        console = Console(no_color=True)
        console._is_tty = True
        console.working(done_count=1, agent_name="Codex")
        output = capsys.readouterr().out
        assert "Codex reviewing..." in output

    def test_iteration_info_tty(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test iteration info for TTY output."""
        console = Console(no_color=True)
        console._is_tty = True
        console.iteration_info(5, 20, 0)
        output = capsys.readouterr().out
        assert "Iteration:" in output
        assert "5" in output
        # Status line removed - box title shows working/reviewing state

    def test_iteration_info_tty_shows_spec_path(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test iteration info shows spec path in TTY mode."""
        console = Console(no_color=True)
        console._is_tty = True
        console.iteration_info(1, 20, 0, spec_path="specs/api.spec.md")
        output = capsys.readouterr().out
        assert "Spec:" in output
        assert "specs/api.spec.md" in output

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

    def test_rotation_complete_tty_agent_removed(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test rotation complete with agent removal for TTY."""
        console = Console(no_color=True)
        console._is_tty = True
        console.rotation_complete(
            Status.ROTATE,
            ["file1.py"],
            0,
            agent_removals=(("Claude", "quota exceeded"),),
        )
        output = capsys.readouterr().out
        assert "Agent:" in output
        assert "Claude removed (quota exceeded)" in output

    def test_rotation_complete_tty_multiple_agent_removals(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test rotation complete with multiple agent removals for TTY."""
        console = Console(no_color=True)
        console._is_tty = True
        console.rotation_complete(
            Status.ROTATE,
            [],
            0,
            agent_removals=(("Claude", "rate limit"), ("Codex", "quota exceeded")),
        )
        output = capsys.readouterr().out
        assert "Claude removed (rate limit)" in output
        assert "Codex removed (quota exceeded)" in output

    def test_rotation_complete_tty_codex_reset_time_reason(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test TTY output preserves Codex reset-time exhaustion details."""
        console = Console(no_color=True)
        console._is_tty = True
        console.rotation_complete(
            Status.ROTATE,
            [],
            0,
            agent_removals=(("Codex", "usage limit reached (resets in 33 minutes)"),),
        )
        output = capsys.readouterr().out
        assert "Codex removed (usage limit reached (resets in 33 minutes))" in output

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

    def test_rotation_complete_tty_with_duration(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test rotation complete with duration for TTY."""
        console = Console(no_color=True)
        console._is_tty = True
        console.rotation_complete(Status.ROTATE, ["file1.py", "file2.py"], 0, duration=45.0)
        output = capsys.readouterr().out
        assert "ROTATE" in output
        assert "2 files changed" in output
        assert "Time:         45s" in output

    def test_rotation_complete_tty_duration_ordering(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Time line appears after files and before removals/verification in TTY."""
        console = Console(no_color=True)
        console._is_tty = True
        console.rotation_complete(
            Status.DONE,
            ["file1.py"],
            1,
            agent_removals=(("Codex", "rate limit"),),
            duration=133.0,
        )
        output = capsys.readouterr().out
        files_idx = output.index("Files:        1 file changed")
        time_idx = output.index("Time:         2m 13s")
        agent_idx = output.index("Agent:        Codex removed (rate limit)")
        verify_idx = output.index("Verification: 1/3 [●○○]")
        assert files_idx < time_idx < agent_idx < verify_idx

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
        assert "handoffs" in output
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
        assert "handoffs" in output
        assert "ralph run" in output
        assert "ralph reset" in output
        assert "─" in output

    def test_all_agents_exhausted_tty(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test all agents exhausted for TTY output."""
        console = Console(no_color=True)
        console._is_tty = True
        console.all_agents_exhausted()
        output = capsys.readouterr().out
        assert "AGENTS EXHAUSTED" in output
        assert "rate limited" in output.lower()
        assert "ralph run" in output
        assert "─" in output

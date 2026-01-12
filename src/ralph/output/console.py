"""Terminal output for Ralph."""

from __future__ import annotations

import sys
from collections.abc import Callable

from ralph.core.state import Status
from ralph.output.colors import ColorContext


class Console:
    """Console output handler."""

    BOX_WIDTH = 57  # Inner width of boxes

    def __init__(self, no_color: bool = False):
        # Pass None to ColorContext to let it auto-detect from NO_COLOR env and TTY,
        # unless no_color is explicitly True
        use_colors = False if no_color else None
        self._colors = ColorContext(use_colors=use_colors)
        self._is_tty = sys.stdout.isatty()

    @property
    def is_tty(self) -> bool:
        return self._is_tty

    def _print(self, message: str = "") -> None:
        print(message)

    def _box_top(self, title: str, color_fn: Callable[[str], str] | None = None) -> str:
        """Create box top with title: ╭── title ─────────╮"""
        if color_fn is None:
            color_fn = self._colors.cyan
        padding = self.BOX_WIDTH - len(title) - 4  # 4 for "── " and " "
        return color_fn(f"  ╭── {title} " + "─" * max(padding, 1) + "╮")

    def _box_mid(self, title: str, color_fn: Callable[[str], str] | None = None) -> str:
        """Create box middle divider: ├── title ─────────┤"""
        if color_fn is None:
            color_fn = self._colors.cyan
        padding = self.BOX_WIDTH - len(title) - 4
        return color_fn(f"  ├── {title} " + "─" * max(padding, 1) + "┤")

    def _box_bottom(self, color_fn: Callable[[str], str] | None = None) -> str:
        """Create box bottom: ╰─────────────────╯"""
        if color_fn is None:
            color_fn = self._colors.cyan
        return color_fn("  ╰" + "─" * self.BOX_WIDTH + "╯")

    def _box_line(self, content: str, color_fn: Callable[[str], str] | None = None) -> str:
        """Create a box content line: │  content         │"""
        if color_fn is None:
            color_fn = self._colors.cyan
        # Calculate visible length (content may have ANSI codes)
        visible_len = len(self._strip_ansi(content))
        padding = self.BOX_WIDTH - visible_len - 2  # 2 for leading spaces
        return color_fn("  │") + f"  {content}" + " " * max(padding, 0) + color_fn("│")

    def _strip_ansi(self, text: str) -> str:
        """Remove ANSI escape codes for length calculation."""
        import re

        return re.sub(r"\x1b\[[0-9;]*m", "", text)

    def _verification_circles(self, done_count: int, total: int = 3) -> str:
        """Create verification circles like [●●○]"""
        filled = "●" * done_count
        empty = "○" * (total - done_count)
        return f"[{filled}{empty}]"

    def banner(self) -> None:
        """Print the Ralph banner at start."""
        if self._is_tty:
            c = self._colors.cyan
            line = "─" * self.BOX_WIDTH
            self._print(c(f"  ╭{line}╮"))
            title = self._colors.bold("  RALPH LOOP")
            padding = self.BOX_WIDTH - 12  # 12 = len("  RALPH LOOP")
            self._print(c("  │") + title + " " * padding + c("│"))
            desc = "  Autonomous development with context rotation"
            desc_padding = self.BOX_WIDTH - len(desc)
            self._print(c("  │") + desc + " " * desc_padding + c("│"))
            self._print(c(f"  ╰{line}╯"))
            self._print()

    def working(self, done_count: int = 0) -> None:
        """Show that Claude is working/reviewing - opens the iteration box."""
        if self._is_tty:
            title = "Claude reviewing..." if done_count > 0 else "Claude working..."
            self._print(self._box_top(title))

    def iteration_info(self, iteration: int, max_iter: int, done_count: int) -> None:
        """Print iteration info inside the box."""
        review_tag = self._colors.magenta(" [REVIEW]") if done_count > 0 else ""

        if self._is_tty:
            iter_str = f"{self._colors.cyan(str(iteration))}/{max_iter}{review_tag}"
            self._print(self._box_line(f"Iteration:    {iter_str}"))
        else:
            mode = " [REVIEW]" if done_count > 0 else ""
            self._print(f"[ralph] ─── Rotation {iteration}/{max_iter}{mode} ───")

    def rotation_complete(
        self,
        status: Status,
        files_changed: list[str],
        done_count: int,
    ) -> None:
        """Print rotation completion and close the box."""
        change_count = len(files_changed)

        if self._is_tty:
            self._print(self._box_mid("Rotation complete"))

            # Color the result based on status
            if status == Status.DONE:
                result_str = self._colors.green("DONE")
            elif status == Status.STUCK:
                result_str = self._colors.red("STUCK")
            elif status == Status.ROTATE:
                result_str = self._colors.yellow("ROTATE")
            else:
                result_str = status.value

            self._print(self._box_line(f"Result:       {result_str}"))

            # Consistent format: "no changes" / "1 file changed" / "N files changed"
            if change_count == 0:
                self._print(self._box_line("Files:        no changes"))
            elif change_count == 1:
                files_str = self._colors.yellow("1 file changed")
                self._print(self._box_line(f"Files:        {files_str}"))
            else:
                files_str = self._colors.yellow(f"{change_count} files changed")
                self._print(self._box_line(f"Files:        {files_str}"))

            # Show verification status for DONE
            if status == Status.DONE:
                circles = self._verification_circles(done_count)
                if done_count >= 3:
                    verify_str = self._colors.green(f"{done_count}/3 {circles}")
                else:
                    verify_str = self._colors.magenta(f"{done_count}/3 {circles}")
                self._print(self._box_line(f"Verification: {verify_str}"))

        else:
            if change_count == 0:
                changes_str = "no changes"
            elif change_count == 1:
                changes_str = "1 file changed"
            else:
                changes_str = f"{change_count} files changed"
            self._print(f"[ralph] Result: {status.value} ({changes_str})")
            if status == Status.DONE:
                circles = self._verification_circles(done_count)
                self._print(f"[ralph] Verification: {done_count}/3 {circles}")

    def test_result(self, cmd: str, exit_code: int, passed: bool) -> None:
        """Print test command result inside the box."""
        if self._is_tty:
            result_str = self._colors.green("passed") if passed else self._colors.red("failed")
            self._print(self._box_line(f"Tests:        {cmd} → {result_str}"))
        else:
            result_str = "passed" if passed else "FAILED"
            self._print(f"[ralph] Tests: {result_str} (exit code {exit_code})")

    def close_iteration(self) -> None:
        """Close the iteration box."""
        if self._is_tty:
            self._print(self._box_bottom())
            self._print()

    def goal_achieved(self, iterations: int, duration_str: str) -> None:
        """Print goal achieved message."""
        if self._is_tty:
            line = "─" * self.BOX_WIDTH
            green = self._colors.green
            self._print()
            self._print(green(f"  ╭{line}╮"))
            title = self._colors.bold(green("  ✓ COMPLETE"))
            padding = self.BOX_WIDTH - 12
            self._print(green("  │") + title + " " * padding + green("│"))
            msg = f"  Goal achieved after {iterations} iterations (3/3 verified)"
            msg_padding = self.BOX_WIDTH - len(msg)
            self._print(green("  │") + msg + " " * msg_padding + green("│"))
            time_msg = f"  Time: {duration_str}"
            time_padding = self.BOX_WIDTH - len(time_msg)
            self._print(green("  │") + time_msg + " " * time_padding + green("│"))
            self._print(green(f"  ╰{line}╯"))
            self._print()
        else:
            self._print(f"[ralph] Goal achieved ({iterations} iterations, {duration_str})")

    def stuck(self) -> None:
        """Print stuck message."""
        if self._is_tty:
            line = "─" * self.BOX_WIDTH
            red = self._colors.red
            self._print()
            self._print(red(f"  ╭{line}╮"))
            title = self._colors.bold(red("  ✗ BLOCKED"))
            padding = self.BOX_WIDTH - 11
            self._print(red("  │") + title + " " * padding + red("│"))
            msg = "  Human input needed"
            msg_padding = self.BOX_WIDTH - len(msg)
            self._print(red("  │") + msg + " " * msg_padding + red("│"))
            self._print(red(f"  ╰{line}╯"))
            self._print()
            self._print("  Next steps:")
            self._print("    1. Read .ralph/handoff.md for what's blocking")
            self._print("    2. Fix the issue or provide guidance")
            self._print("    3. Run: ralph run")
            self._print()
        else:
            self._print("[ralph] BLOCKED - see .ralph/handoff.md for next steps")

    def max_iterations(self, max_iter: int) -> None:
        """Print max iterations reached message."""
        if self._is_tty:
            line = "─" * self.BOX_WIDTH
            yellow = self._colors.yellow
            self._print()
            self._print(yellow(f"  ╭{line}╮"))
            title = self._colors.bold(yellow("  ⚠ MAX ITERATIONS"))
            padding = self.BOX_WIDTH - 18
            self._print(yellow("  │") + title + " " * padding + yellow("│"))
            msg = f"  Reached limit ({max_iter}/{max_iter})"
            msg_padding = self.BOX_WIDTH - len(msg)
            self._print(yellow("  │") + msg + " " * msg_padding + yellow("│"))
            self._print(yellow(f"  ╰{line}╯"))
            self._print()
            self._print("  Check .ralph/handoff.md for current state")
            self._print("  To continue: ralph run")
            self._print("  To reset:    ralph reset")
            self._print()
        else:
            self._print(f"[ralph] Max iterations reached ({max_iter})")

    def status_display(
        self,
        iteration: int,
        max_iter: int,
        status: Status,
        done_count: int,
        goal_preview: str | None = None,
    ) -> None:
        """Print the status display with box styling."""
        if self._is_tty:
            self._print(self._box_top("Ralph Status"))

            # Iteration line
            iter_str = f"{iteration}/{max_iter}"
            self._print(self._box_line(f"Iteration:    {iter_str}"))

            # Last signal with color
            if status == Status.DONE:
                status_str = self._colors.green(status.value)
            elif status == Status.STUCK:
                status_str = self._colors.red(status.value)
            elif status == Status.ROTATE:
                status_str = self._colors.yellow(status.value)
            elif status == Status.CONTINUE:
                status_str = self._colors.cyan(status.value)
            else:
                status_str = status.value

            self._print(self._box_line(f"Last signal:  {status_str}"))

            # Verification
            if done_count > 0 or status == Status.DONE:
                circles = self._verification_circles(done_count)
                verify_str = f"{done_count}/3 {circles}"
                self._print(self._box_line(f"Verification: {verify_str}"))
            else:
                self._print(self._box_line("Verification: not started"))

            self._print(self._box_bottom())

            # Goal preview below box
            if goal_preview:
                self._print()
                self._print(self._colors.dim("Goal:") + f" {goal_preview}")

            # Next step hint
            self._print()
            self._print(self._colors.dim("Next:") + " ralph run")
        else:
            # Non-TTY: simple output
            self._print(f"[ralph] Status: iteration {iteration}/{max_iter}, {status.value}")
            if done_count > 0 or status == Status.DONE:
                circles = self._verification_circles(done_count)
                self._print(f"[ralph] Verification: {done_count}/3 {circles}")
            if goal_preview:
                self._print(f"[ralph] Goal: {goal_preview}")

    def history_list(
        self,
        entries: list[tuple[int, str | None, str | None, int, bool]],
    ) -> None:
        """Print history list with box styling.

        Each entry is: (rotation_num, timestamp, status, files_changed, is_complete)
        """
        if self._is_tty:
            self._print(self._box_top("Ralph History"))

            for rot_num, timestamp, status, files_changed, is_complete in entries:
                # Format timestamp (show just time if available)
                if timestamp:
                    # Extract time portion
                    ts = timestamp.replace("T", " ").split(".")[0]
                    # Just show time part
                    ts_parts = ts.split(" ")
                    time_part = ts_parts[1] if len(ts_parts) > 1 else ts
                    # Truncate to HH:MM
                    time_str = time_part[:5]
                else:
                    time_str = "??:??"

                # Color status
                if status == "DONE":
                    status_str = self._colors.green(status)
                elif status == "STUCK":
                    status_str = self._colors.red(status)
                elif status == "ROTATE":
                    status_str = self._colors.yellow(status)
                elif status == "CONTINUE":
                    status_str = self._colors.cyan(status)
                else:
                    status_str = status or "???"

                # Format files changed
                if files_changed == 0:
                    files_str = "no changes"
                elif files_changed == 1:
                    files_str = "1 file changed"
                else:
                    files_str = f"{files_changed} files changed"

                # Build the line
                line = f"{rot_num:3d}. {time_str}  {status_str:8s}  {files_str}"
                if is_complete:
                    line += "  " + self._colors.green("✓ COMPLETE")

                self._print(self._box_line(line))

            self._print(self._box_bottom())
        else:
            # Non-TTY: simple output
            self._print("[ralph] ─── History ───")
            for rot_num, _timestamp, status, files_changed, is_complete in entries:
                if files_changed == 0:
                    files_str = "no changes"
                elif files_changed == 1:
                    files_str = "1 file changed"
                else:
                    files_str = f"{files_changed} files changed"
                complete_mark = " [COMPLETE]" if is_complete else ""
                self._print(f"[ralph] {rot_num}. {status} ({files_str}){complete_mark}")

    def error(self, message: str, hint: str | None = None) -> None:
        """Print an error message with optional hint."""
        self._print(self._colors.red(f"Error: {message}"))
        if hint:
            self._print()
            self._print(hint)

    def warning(self, message: str) -> None:
        """Print a warning message."""
        self._print(self._colors.yellow(f"Warning: {message}"))

    def info(self, message: str) -> None:
        """Print an info message."""
        self._print(message)

    def success(self, message: str) -> None:
        """Print a success message."""
        self._print(self._colors.green(message))

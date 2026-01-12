"""Tests for color handling."""

from __future__ import annotations

import pytest

from ralph.output.colors import (
    BOLD,
    CYAN,
    GREEN,
    MAGENTA,
    RED,
    RESET,
    WHITE,
    YELLOW,
    ColorContext,
    should_use_colors,
)


class TestShouldUseColors:
    """Tests for should_use_colors function."""

    def test_no_color_env_disables(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test NO_COLOR environment variable disables colors."""
        monkeypatch.setenv("NO_COLOR", "1")
        assert should_use_colors() is False

    def test_no_color_env_empty_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test NO_COLOR with empty string still disables."""
        monkeypatch.setenv("NO_COLOR", "")
        # Empty string is falsy, so colors should be determined by TTY
        # In test environment, stdout is not a TTY
        assert should_use_colors() is False


class TestColorContext:
    """Tests for ColorContext class."""

    def test_colors_disabled_returns_plain_text(self) -> None:
        """Test that colors disabled returns plain text."""
        ctx = ColorContext(use_colors=False)
        assert ctx.red("hello") == "hello"
        assert ctx.green("world") == "world"
        assert ctx.yellow("test") == "test"
        assert ctx.cyan("foo") == "foo"
        assert ctx.white("bar") == "bar"
        assert ctx.magenta("baz") == "baz"
        assert ctx.bold("qux") == "qux"

    def test_colors_enabled_wraps_with_codes(self) -> None:
        """Test that colors enabled wraps text with ANSI codes."""
        ctx = ColorContext(use_colors=True)
        assert ctx.red("hello") == f"{RED}hello{RESET}"
        assert ctx.green("world") == f"{GREEN}world{RESET}"
        assert ctx.yellow("test") == f"{YELLOW}test{RESET}"
        assert ctx.cyan("foo") == f"{CYAN}foo{RESET}"
        assert ctx.white("bar") == f"{WHITE}bar{RESET}"
        assert ctx.magenta("baz") == f"{MAGENTA}baz{RESET}"
        assert ctx.bold("qux") == f"{BOLD}qux{RESET}"

    def test_use_colors_property(self) -> None:
        """Test use_colors property returns correct value."""
        ctx_enabled = ColorContext(use_colors=True)
        ctx_disabled = ColorContext(use_colors=False)
        assert ctx_enabled.use_colors is True
        assert ctx_disabled.use_colors is False

    def test_default_uses_should_use_colors(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that default behavior uses should_use_colors."""
        monkeypatch.setenv("NO_COLOR", "1")
        ctx = ColorContext()
        assert ctx.use_colors is False

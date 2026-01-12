"""Color handling for terminal output."""

from __future__ import annotations

import os
import sys

# ANSI color codes
RESET = "\033[0m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
WHITE = "\033[37m"
BOLD = "\033[1m"
DIM = "\033[2m"


def should_use_colors() -> bool:
    """Determine if colors should be used."""
    # Check NO_COLOR environment variable
    if os.environ.get("NO_COLOR"):
        return False

    # Check if stdout is a TTY
    return sys.stdout.isatty()


class ColorContext:
    """Context for colored output."""

    def __init__(self, use_colors: bool | None = None):
        if use_colors is None:
            use_colors = should_use_colors()
        self._use_colors = use_colors

    @property
    def use_colors(self) -> bool:
        return self._use_colors

    def _wrap(self, text: str, code: str) -> str:
        if not self._use_colors:
            return text
        return f"{code}{text}{RESET}"

    def red(self, text: str) -> str:
        return self._wrap(text, RED)

    def green(self, text: str) -> str:
        return self._wrap(text, GREEN)

    def yellow(self, text: str) -> str:
        return self._wrap(text, YELLOW)

    def cyan(self, text: str) -> str:
        return self._wrap(text, CYAN)

    def white(self, text: str) -> str:
        return self._wrap(text, WHITE)

    def magenta(self, text: str) -> str:
        return self._wrap(text, MAGENTA)

    def bold(self, text: str) -> str:
        return self._wrap(text, BOLD)

    def dim(self, text: str) -> str:
        return self._wrap(text, DIM)

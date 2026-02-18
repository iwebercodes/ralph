"""Shared global flag callbacks for subcommands."""

from __future__ import annotations

import typer

from ralph import __version__
from ralph.output.about import get_about_text
from ralph.output.console import Console


def version_callback(value: bool) -> None:
    """Print version and exit when --version is provided."""
    if value:
        console = Console()
        console.print(f"ralph {__version__}")
        raise typer.Exit(0)


def about_callback(value: bool) -> None:
    """Print about text and exit when --about is provided."""
    if value:
        console = Console()
        console.print(get_about_text())
        raise typer.Exit(0)

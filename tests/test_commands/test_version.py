"""Tests for ralph --version flag."""

from __future__ import annotations

from typer.testing import CliRunner

from ralph import __version__
from ralph.cli import app

runner = CliRunner()


def test_version_flag_exits_successfully() -> None:
    """--version flag exits cleanly."""
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0


def test_version_flag_outputs_version() -> None:
    """--version outputs the version in expected format."""
    result = runner.invoke(app, ["--version"])

    assert f"ralph {__version__}" in result.output


def test_version_flag_matches_init_version() -> None:
    """Version output matches __version__ from ralph package."""
    result = runner.invoke(app, ["--version"])

    # The output should be "ralph X.Y.Z" and match __version__
    assert __version__ in result.output


def test_short_version_flag() -> None:
    """-V short flag works the same as --version."""
    result = runner.invoke(app, ["-V"])

    assert result.exit_code == 0
    assert f"ralph {__version__}" in result.output


def test_version_help_shows_option() -> None:
    """Help text shows --version option."""
    result = runner.invoke(app, ["--help"])

    # Check for "version" without dashes - ANSI codes can split "--version"
    assert "version" in result.output.lower()


def test_version_and_subcommand() -> None:
    """Subcommands still work normally."""
    result = runner.invoke(app, ["status", "--help"])

    assert result.exit_code == 0

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


def test_no_short_version_flag() -> None:
    """No short flag for version - spec doesn't define one."""
    result = runner.invoke(app, ["-V"])

    # Should fail or show help, not show version
    assert result.exit_code != 0 or f"ralph {__version__}" not in result.output


def test_version_help_shows_option() -> None:
    """Help text shows --version option."""
    result = runner.invoke(app, ["--help"])

    # Check for "version" without dashes - ANSI codes can split "--version"
    assert "version" in result.output.lower()


def test_global_help_hides_completion_flags() -> None:
    """Global help should not expose completion management flags."""
    result = runner.invoke(app, ["--help"])

    assert "--install-completion" not in result.output
    assert "--show-completion" not in result.output


def test_version_and_subcommand() -> None:
    """Subcommands still work normally."""
    result = runner.invoke(app, ["status", "--help"])

    assert result.exit_code == 0


def test_version_works_in_subcommand_context() -> None:
    """--version should exit before executing subcommand logic."""
    result = runner.invoke(app, ["status", "--version"])

    assert result.exit_code == 0
    assert f"ralph {__version__}" in result.output

"""Tests for ralph --about flag."""

from __future__ import annotations

from typer.testing import CliRunner

from ralph.cli import app

runner = CliRunner()


def test_about_runs_successfully() -> None:
    """--about flag exits cleanly."""
    result = runner.invoke(app, ["--about"])

    assert result.exit_code == 0


def test_about_contains_commands() -> None:
    """Output mentions ralph init, ralph run, ralph status, etc."""
    result = runner.invoke(app, ["--about"])

    assert "ralph init" in result.output
    assert "ralph run" in result.output
    assert "ralph status" in result.output
    assert "ralph reset" in result.output
    assert "ralph history" in result.output


def test_about_contains_exit_codes() -> None:
    """Output explains exit codes 0, 2, 3."""
    result = runner.invoke(app, ["--about"])

    # Should explain what each exit code means
    assert "EXIT CODES" in result.output
    assert "0" in result.output
    assert "2" in result.output
    assert "3" in result.output
    assert "Success" in result.output
    assert "Stuck" in result.output


def test_about_contains_prompt_md() -> None:
    """Output explains what to put in PROMPT.md."""
    result = runner.invoke(app, ["--about"])

    assert "PROMPT.md" in result.output
    assert "goal" in result.output.lower()
    assert "success criteria" in result.output.lower()


def test_about_contains_options() -> None:
    """Output mentions key options like --max, --test-cmd."""
    result = runner.invoke(app, ["--about"])

    assert "--max" in result.output
    assert "--test-cmd" in result.output
    assert "--force" in result.output
    assert "--json" in result.output
    assert "--keep-guardrails" in result.output


def test_about_is_substantial() -> None:
    """Output is at least 1000 characters (not a stub)."""
    result = runner.invoke(app, ["--about"])

    assert len(result.output) > 1000


def test_about_does_not_contain_internal_protocol() -> None:
    """Output should NOT explain status signals in detail.

    The invoking agent doesn't need to know about CONTINUE/ROTATE/DONE/STUCK
    signals — that's for the supervised agent under Ralph's control.
    """
    result = runner.invoke(app, ["--about"])

    # Should NOT have a section explaining signals to write
    assert "Write one of these" not in result.output
    assert "Signal ROTATE" not in result.output
    # Brief mention of internal protocol is fine, but no detailed instructions
    assert ".ralph/status" not in result.output or "write" not in result.output.lower()


def test_about_no_fake_urls() -> None:
    """Output should not contain unverified URLs."""
    result = runner.invoke(app, ["--about"])

    # Should not contain any github URLs (the fake one was removed)
    assert "github.com" not in result.output.lower()
    # Should not contain any URLs at all (safer)
    assert "https://" not in result.output


def test_about_contains_verification_info() -> None:
    """Output explains the 3x verification process."""
    result = runner.invoke(app, ["--about"])

    # Should mention verification happens 3 times
    assert "3" in result.output
    assert "verif" in result.output.lower()


def test_help_still_works() -> None:
    """--help still shows command help."""
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Commands" in result.output
    assert "init" in result.output
    assert "run" in result.output


def test_no_args_shows_help() -> None:
    """Running ralph with no args shows help."""
    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "Commands" in result.output


def test_subcommands_still_work() -> None:
    """Subcommands work normally after adding --about."""
    # Test that init can be invoked (it will fail because no project, but that's expected)
    result = runner.invoke(app, ["init", "--help"])

    assert result.exit_code == 0
    assert "Initialize Ralph" in result.output

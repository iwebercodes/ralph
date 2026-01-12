"""Tests for ignore pattern handling."""

from __future__ import annotations

from pathlib import Path

from ralph.core.ignore import DEFAULT_IGNORES, create_spec, load_ignore_patterns, should_ignore


def test_default_ignores() -> None:
    """Test default ignore patterns are present."""
    assert ".ralph/" in DEFAULT_IGNORES
    assert ".git/" in DEFAULT_IGNORES
    assert "node_modules/" in DEFAULT_IGNORES
    assert "__pycache__/" in DEFAULT_IGNORES


def test_load_ignore_patterns_no_file(temp_project: Path) -> None:
    """Test loading patterns when no .ralphignore exists."""
    patterns = load_ignore_patterns(temp_project)
    assert ".ralph/" in patterns
    assert ".git/" in patterns


def test_load_ignore_patterns_with_file(temp_project: Path) -> None:
    """Test loading patterns from .ralphignore."""
    ralphignore = temp_project / ".ralphignore"
    ralphignore.write_text("*.log\nbuild/\n# comment\n\n!important.log")

    patterns = load_ignore_patterns(temp_project)

    # Should include defaults
    assert ".ralph/" in patterns

    # Should include custom patterns
    assert "*.log" in patterns
    assert "build/" in patterns
    assert "!important.log" in patterns

    # Should not include comments or blank lines
    assert "# comment" not in patterns
    assert "" not in patterns


def test_should_ignore_glob_pattern() -> None:
    """Test ignoring files by glob pattern."""
    spec = create_spec(["*.log"])

    assert should_ignore("debug.log", spec) is True
    assert should_ignore("app.py", spec) is False


def test_should_ignore_directory_pattern() -> None:
    """Test ignoring directories."""
    spec = create_spec(["node_modules/"])

    assert should_ignore("node_modules/pkg/index.js", spec) is True
    assert should_ignore("node_modules_backup/file.js", spec) is False


def test_should_ignore_double_star() -> None:
    """Test ** pattern matching."""
    spec = create_spec(["**/__pycache__/"])

    assert should_ignore("__pycache__/foo.pyc", spec) is True
    assert should_ignore("src/__pycache__/bar.pyc", spec) is True
    assert should_ignore("src/deep/nested/__pycache__/baz.pyc", spec) is True


def test_should_ignore_ralph_dir() -> None:
    """Test .ralph/ directory is ignored."""
    spec = create_spec(DEFAULT_IGNORES)

    assert should_ignore(".ralph/status", spec) is True
    assert should_ignore(".ralph/handoff.md", spec) is True
    assert should_ignore(".ralph/history/001.log", spec) is True


def test_should_ignore_preserves_code_files() -> None:
    """Test that normal code files are not ignored."""
    spec = create_spec(DEFAULT_IGNORES)

    assert should_ignore("src/main.py", spec) is False
    assert should_ignore("tests/test_foo.py", spec) is False
    assert should_ignore("README.md", spec) is False

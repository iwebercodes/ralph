"""Gitignore-style pattern matching for .ralphignore."""

from __future__ import annotations

from pathlib import Path

import pathspec

DEFAULT_IGNORES = [
    ".ralph/",
    ".git/",
    ".venv/",
    "venv/",
    "node_modules/",
    "__pycache__/",
    "*.pyc",
    ".DS_Store",
    "*.swp",
    "*.swo",
    "*~",
]


def load_ignore_patterns(root: Path | None = None) -> list[str]:
    """Load ignore patterns from .ralphignore and defaults."""
    if root is None:
        root = Path.cwd()

    patterns = list(DEFAULT_IGNORES)

    ralphignore = root / ".ralphignore"
    if ralphignore.exists():
        content = ralphignore.read_text()
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line)

    return patterns


def create_spec(patterns: list[str]) -> pathspec.PathSpec:
    """Create a pathspec from patterns."""
    return pathspec.PathSpec.from_lines("gitignore", patterns)


def should_ignore(path: str | Path, spec: pathspec.PathSpec) -> bool:
    """Check if a path should be ignored."""
    path_str = str(path)
    return spec.match_file(path_str)

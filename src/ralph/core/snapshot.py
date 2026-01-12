"""File change detection through snapshots."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pathspec

from ralph.core.ignore import create_spec, load_ignore_patterns


def hash_file(path: Path) -> str:
    """Compute MD5 hash of a file's contents."""
    hasher = hashlib.md5()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except OSError:
        return ""


def take_snapshot(
    root: Path | None = None, spec: pathspec.PathSpec | None = None
) -> dict[str, str]:
    """Take a snapshot of all tracked files.

    Returns a mapping of relative file path to content hash.
    """
    if root is None:
        root = Path.cwd()

    if spec is None:
        patterns = load_ignore_patterns(root)
        spec = create_spec(patterns)

    snapshot: dict[str, str] = {}

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        rel_path = path.relative_to(root)
        rel_str = rel_path.as_posix()

        if spec.match_file(rel_str):
            continue

        file_hash = hash_file(path)
        if file_hash:
            snapshot[rel_str] = file_hash

    return snapshot


def compare_snapshots(before: dict[str, str], after: dict[str, str]) -> list[str]:
    """Compare two snapshots and return list of changed file paths.

    Includes modified, new, and deleted files.
    """
    changed: set[str] = set()

    # Check for modified and new files
    for path, hash_value in after.items():
        if path not in before or before[path] != hash_value:
            changed.add(path)

    # Check for deleted files
    for path in before:
        if path not in after:
            changed.add(path)

    return sorted(changed)


def serialize_snapshot(snapshot: dict[str, str]) -> str:
    """Serialize a snapshot to a string for storage."""
    lines = [f"{path}\t{hash_val}" for path, hash_val in sorted(snapshot.items())]
    return "\n".join(lines)


def deserialize_snapshot(content: str) -> dict[str, str]:
    """Deserialize a snapshot from storage."""
    snapshot: dict[str, str] = {}
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t", 1)
        if len(parts) == 2:
            snapshot[parts[0]] = parts[1]
    return snapshot

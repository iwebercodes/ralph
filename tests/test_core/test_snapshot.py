"""Tests for snapshot functionality."""

from __future__ import annotations

from pathlib import Path

from ralph.core.ignore import create_spec
from ralph.core.snapshot import (
    compare_snapshots,
    deserialize_snapshot,
    hash_file,
    serialize_snapshot,
    take_snapshot,
)


def test_hash_file(temp_project: Path) -> None:
    """Test file hashing produces consistent results."""
    test_file = temp_project / "test.txt"
    test_file.write_text("hello world")

    hash1 = hash_file(test_file)
    hash2 = hash_file(test_file)

    assert hash1 == hash2
    assert len(hash1) == 32  # MD5 hex digest length


def test_hash_file_different_content(temp_project: Path) -> None:
    """Test different content produces different hash."""
    file1 = temp_project / "file1.txt"
    file2 = temp_project / "file2.txt"
    file1.write_text("content1")
    file2.write_text("content2")

    assert hash_file(file1) != hash_file(file2)


def test_hash_file_nonexistent(temp_project: Path) -> None:
    """Test hashing nonexistent file returns empty string."""
    assert hash_file(temp_project / "nonexistent.txt") == ""


def test_take_snapshot(temp_project: Path) -> None:
    """Test taking a snapshot of files."""
    (temp_project / "file1.py").write_text("content1")
    (temp_project / "file2.py").write_text("content2")
    subdir = temp_project / "subdir"
    subdir.mkdir()
    (subdir / "file3.py").write_text("content3")

    # Create spec that ignores nothing extra
    spec = create_spec([".ralph/"])

    snapshot = take_snapshot(temp_project, spec)

    assert "file1.py" in snapshot
    assert "file2.py" in snapshot
    assert "subdir/file3.py" in snapshot


def test_take_snapshot_ignores_patterns(temp_project: Path) -> None:
    """Test snapshot respects ignore patterns."""
    (temp_project / "file.py").write_text("code")
    (temp_project / "debug.log").write_text("log")

    spec = create_spec(["*.log"])

    snapshot = take_snapshot(temp_project, spec)

    assert "file.py" in snapshot
    assert "debug.log" not in snapshot


def test_compare_snapshots_no_changes() -> None:
    """Test comparing identical snapshots."""
    snapshot = {"file.py": "abc123"}
    changes = compare_snapshots(snapshot, snapshot)
    assert changes == []


def test_compare_snapshots_modified_file() -> None:
    """Test detecting modified files."""
    before = {"file.py": "abc123"}
    after = {"file.py": "def456"}

    changes = compare_snapshots(before, after)
    assert changes == ["file.py"]


def test_compare_snapshots_new_file() -> None:
    """Test detecting new files."""
    before = {"file1.py": "abc123"}
    after = {"file1.py": "abc123", "file2.py": "def456"}

    changes = compare_snapshots(before, after)
    assert changes == ["file2.py"]


def test_compare_snapshots_deleted_file() -> None:
    """Test detecting deleted files."""
    before = {"file1.py": "abc123", "file2.py": "def456"}
    after = {"file1.py": "abc123"}

    changes = compare_snapshots(before, after)
    assert changes == ["file2.py"]


def test_compare_snapshots_multiple_changes() -> None:
    """Test detecting multiple changes."""
    before = {"keep.py": "aaa", "modify.py": "bbb", "delete.py": "ccc"}
    after = {"keep.py": "aaa", "modify.py": "bbb_changed", "new.py": "ddd"}

    changes = compare_snapshots(before, after)
    assert sorted(changes) == ["delete.py", "modify.py", "new.py"]


def test_serialize_deserialize_snapshot() -> None:
    """Test serializing and deserializing snapshots."""
    original = {
        "file1.py": "abc123",
        "subdir/file2.py": "def456",
    }

    serialized = serialize_snapshot(original)
    deserialized = deserialize_snapshot(serialized)

    assert deserialized == original


def test_deserialize_empty() -> None:
    """Test deserializing empty content."""
    assert deserialize_snapshot("") == {}
    assert deserialize_snapshot("  \n  \n  ") == {}


def test_take_snapshot_integration(temp_project: Path) -> None:
    """Integration test: take snapshot, make change, detect it."""
    test_file = temp_project / "test.py"
    test_file.write_text("original")

    spec = create_spec([".ralph/"])
    before = take_snapshot(temp_project, spec)

    test_file.write_text("modified")
    after = take_snapshot(temp_project, spec)

    changes = compare_snapshots(before, after)
    assert changes == ["test.py"]

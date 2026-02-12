"""Focused tests for verification counter behavior."""

from __future__ import annotations

from pathlib import Path

from ralph.core.loop import handle_status
from ralph.core.state import (
    MultiSpecState,
    SpecProgress,
    Status,
    ensure_state,
    read_multi_state,
    write_multi_state,
)


def _state(
    done_counts: list[int],
    last_statuses: list[str | None],
    current_index: int = 0,
) -> MultiSpecState:
    specs = [
        SpecProgress(
            path=f"spec-{idx}.spec.md",
            done_count=done_count,
            last_status=last_status,
        )
        for idx, (done_count, last_status) in enumerate(
            zip(done_counts, last_statuses, strict=True)
        )
    ]
    return MultiSpecState(
        version=1,
        iteration=1,
        status=Status.CONTINUE,
        current_index=current_index,
        specs=specs,
    )


def test_new_specs_start_at_zero(initialized_project: Path) -> None:
    """New specs always start at 0/3."""
    state = ensure_state(["PROMPT.md", "specs/new.spec.md"], initialized_project)
    assert [spec.done_count for spec in state.specs] == [0, 0]


def test_done_without_changes_increments_only_current_spec() -> None:
    """DONE without changes increments current spec only."""
    state = _state([1, 2], [Status.DONE.value, Status.DONE.value], current_index=0)

    _, _, updated, done_count = handle_status(state, 0, Status.DONE, [], "hash-a")

    assert done_count == 2
    assert updated.specs[0].done_count == 2
    assert updated.specs[1].done_count == 2


def test_done_with_changes_resets_current_to_one_and_downgrades_other_three_of_three() -> None:
    """DONE with file changes resets current to 1 and only downgrades other 3/3 specs."""
    state = _state(
        [3, 2, 1],
        [Status.DONE.value, Status.ROTATE.value, Status.DONE.value],
        current_index=2,
    )

    _, _, updated, done_count = handle_status(state, 2, Status.DONE, ["changed.py"], "hash-c")

    assert done_count == 1
    assert updated.specs[0].done_count == 2  # 3/3 -> 2/3 downgrade
    assert updated.specs[1].done_count == 2  # unchanged (not 3/3)
    assert updated.specs[2].done_count == 1  # current DONE+changes -> 1


def test_non_done_with_changes_resets_current_to_zero_and_downgrades_other_three_of_three() -> None:
    """Non-DONE with file changes resets current to 0 and only downgrades other 3/3 specs."""
    state = _state(
        [3, 1, 2],
        [Status.DONE.value, Status.CONTINUE.value, Status.DONE.value],
        current_index=1,
    )

    _, _, updated, done_count = handle_status(state, 1, Status.ROTATE, ["changed.py"], "hash-b")

    assert done_count == 0
    assert updated.specs[0].done_count == 2  # 3/3 -> 2/3 downgrade
    assert updated.specs[1].done_count == 0  # current non-DONE+changes -> 0
    assert updated.specs[2].done_count == 2  # unchanged (not 3/3)


def test_non_done_without_changes_preserves_counter() -> None:
    """Non-DONE without file changes keeps the counter unchanged."""
    state = _state([2], [Status.DONE.value], current_index=0)

    _, _, updated, done_count = handle_status(state, 0, Status.ROTATE, [], "hash-a")

    assert done_count == 2
    assert updated.specs[0].done_count == 2


def test_stuck_without_changes_preserves_counter() -> None:
    """STUCK without file changes keeps the counter unchanged."""
    state = _state([2], [Status.DONE.value], current_index=0)

    action, exit_code, updated, done_count = handle_status(state, 0, Status.STUCK, [], "hash-a")

    assert action == "exit"
    assert exit_code == 2
    assert done_count == 2
    assert updated.specs[0].done_count == 2


def test_stuck_with_changes_resets_current_to_zero_and_downgrades_other_three_of_three() -> None:
    """STUCK with file changes resets current to 0 and only downgrades other 3/3 specs."""
    state = _state(
        [3, 1, 2],
        [Status.DONE.value, Status.CONTINUE.value, Status.DONE.value],
        current_index=1,
    )

    action, exit_code, updated, done_count = handle_status(
        state, 1, Status.STUCK, ["changed.py"], "hash-b"
    )

    assert action == "exit"
    assert exit_code == 2
    assert done_count == 0
    assert updated.specs[0].done_count == 2  # 3/3 -> 2/3 downgrade
    assert updated.specs[1].done_count == 0  # current STUCK+changes -> 0
    assert updated.specs[2].done_count == 2  # unchanged (not 3/3)


def test_done_count_is_capped_at_three() -> None:
    """Counter never exceeds 3/3."""
    state = _state([3], [Status.DONE.value], current_index=0)

    _, _, updated, done_count = handle_status(state, 0, Status.DONE, [], "hash-a")

    assert done_count == 3
    assert updated.specs[0].done_count == 3


def test_counter_persists_across_restart(initialized_project: Path) -> None:
    """Counter values persist in state.json across process restarts."""
    state = MultiSpecState(
        version=1,
        iteration=7,
        status=Status.DONE,
        current_index=1,
        specs=[
            SpecProgress(path="spec-a.spec.md", done_count=1, last_status=Status.DONE.value),
            SpecProgress(path="spec-b.spec.md", done_count=2, last_status=Status.DONE.value),
        ],
    )
    write_multi_state(state, initialized_project)

    loaded = read_multi_state(initialized_project)
    assert loaded is not None
    assert loaded.specs[0].done_count == 1
    assert loaded.specs[1].done_count == 2


def test_each_spec_keeps_independent_counter_without_file_changes() -> None:
    """Each spec tracks its own counter independently when no files change."""
    state = _state([0, 0], [None, None], current_index=0)

    _, _, state_after_first, done_count_0 = handle_status(state, 0, Status.DONE, [], "hash-a")
    _, _, state_after_second, done_count_1 = handle_status(
        state_after_first, 1, Status.DONE, [], "hash-b"
    )

    assert done_count_0 == 1
    assert done_count_1 == 1
    assert state_after_second.specs[0].done_count == 1
    assert state_after_second.specs[1].done_count == 1


def test_handle_status_with_empty_specs_list() -> None:
    """Handle status safely with empty specs list or invalid index."""
    # Test with empty specs list
    empty_state = MultiSpecState(
        version=1,
        iteration=1,
        status=Status.CONTINUE,
        current_index=0,
        specs=[],
    )

    action, exit_code, updated, done_count = handle_status(empty_state, 0, Status.DONE, [], "hash")

    assert action == "continue"
    assert exit_code is None
    assert done_count == 0
    assert updated.specs == []

    # Test with out-of-bounds index
    state = _state([1], [Status.DONE.value], current_index=0)
    action, exit_code, updated, done_count = handle_status(state, 5, Status.DONE, [], "hash")

    assert action == "continue"
    assert exit_code is None
    assert done_count == 0
    assert updated.specs[0].done_count == 1  # Unchanged

    # Test STUCK with invalid index
    action, exit_code, updated, done_count = handle_status(state, -1, Status.STUCK, [], "hash")

    assert action == "exit"
    assert exit_code == 2
    assert done_count == 0

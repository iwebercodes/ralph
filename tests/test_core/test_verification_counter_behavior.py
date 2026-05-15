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


# ============================================================================
# Scenario tests from spec examples
# ============================================================================


def test_scenario_1_implementation_and_verification() -> None:
    """Example 1: Agent implements feature, then verifies twice without changes.

    Rotation 1: Agent implements feature, returns DONE → 1/3
    Rotation 2: Agent reviews code, returns DONE (no changes) → 2/3
    Rotation 3: Agent reviews again, returns DONE (no changes) → 3/3 ✓
    """
    state = _state([0], [None], current_index=0)

    # Rotation 1: DONE with file changes → 1/3
    _, _, state, done_count = handle_status(state, 0, Status.DONE, ["feature.py"], "hash-1")
    assert done_count == 1
    assert state.specs[0].done_count == 1

    # Rotation 2: DONE without changes → 2/3
    _, _, state, done_count = handle_status(state, 0, Status.DONE, [], "hash-2")
    assert done_count == 2
    assert state.specs[0].done_count == 2

    # Rotation 3: DONE without changes → 3/3
    _, exit_code, state, done_count = handle_status(state, 0, Status.DONE, [], "hash-3")
    assert done_count == 3
    assert state.specs[0].done_count == 3
    assert exit_code == 0  # All specs complete


def test_scenario_2_rotation_without_completion() -> None:
    """Example 2: Agent works on feature, returns ROTATE, then continues.

    Rotation 1: Agent works on feature, returns ROTATE → 0/3 (unchanged)
    Rotation 2: Agent continues work, returns DONE → 1/3
    Rotation 3: Agent reviews, returns DONE (no changes) → 2/3
    """
    state = _state([0], [None], current_index=0)

    # Rotation 1: ROTATE without changes → 0/3 (unchanged)
    _, _, state, done_count = handle_status(state, 0, Status.ROTATE, [], "hash-1")
    assert done_count == 0
    assert state.specs[0].done_count == 0

    # Rotation 2: DONE with file changes → 1/3
    _, _, state, done_count = handle_status(state, 0, Status.DONE, ["feature.py"], "hash-2")
    assert done_count == 1
    assert state.specs[0].done_count == 1

    # Rotation 3: DONE without changes → 2/3
    _, _, state, done_count = handle_status(state, 0, Status.DONE, [], "hash-3")
    assert done_count == 2
    assert state.specs[0].done_count == 2


def test_scenario_3_found_issue_during_verification() -> None:
    """Example 3: Agent implements, then finds and fixes a bug during review.

    Rotation 1: Agent implements, returns DONE → 1/3
    Rotation 2: Agent reviews, finds bug, fixes it, returns DONE → 1/3 (reset due to changes)
    Rotation 3: Agent reviews, returns DONE (no changes) → 2/3
    """
    state = _state([0], [None], current_index=0)

    # Rotation 1: DONE with file changes → 1/3
    _, _, state, done_count = handle_status(state, 0, Status.DONE, ["feature.py"], "hash-1")
    assert done_count == 1
    assert state.specs[0].done_count == 1

    # Rotation 2: DONE with file changes (bug fix) → 1/3 (reset)
    _, _, state, done_count = handle_status(state, 0, Status.DONE, ["feature.py"], "hash-2")
    assert done_count == 1
    assert state.specs[0].done_count == 1

    # Rotation 3: DONE without changes → 2/3
    _, _, state, done_count = handle_status(state, 0, Status.DONE, [], "hash-3")
    assert done_count == 2
    assert state.specs[0].done_count == 2


def test_scenario_4_context_exhaustion_during_verification() -> None:
    """Example 4: Context runs out during verification, different agent finishes it.

    Rotation 1: Agent implements, returns DONE → 1/3
    Rotation 2: Agent reviews, returns DONE (no changes) → 2/3
    Rotation 3: Agent reviews, returns ROTATE (no changes) → 2/3 (unchanged)
    Rotation 4: Different agent reviews, returns DONE (no changes) → 3/3 ✓
    """
    state = _state([0], [None], current_index=0)

    # Rotation 1: DONE with file changes → 1/3
    _, _, state, done_count = handle_status(state, 0, Status.DONE, ["feature.py"], "hash-1")
    assert done_count == 1
    assert state.specs[0].done_count == 1

    # Rotation 2: DONE without changes → 2/3
    _, _, state, done_count = handle_status(state, 0, Status.DONE, [], "hash-2")
    assert done_count == 2
    assert state.specs[0].done_count == 2

    # Rotation 3: ROTATE without changes → 2/3 (unchanged)
    _, _, state, done_count = handle_status(state, 0, Status.ROTATE, [], "hash-3")
    assert done_count == 2
    assert state.specs[0].done_count == 2

    # Rotation 4: DONE without changes → 3/3 ✓
    _, exit_code, state, done_count = handle_status(state, 0, Status.DONE, [], "hash-4")
    assert done_count == 3
    assert state.specs[0].done_count == 3
    assert exit_code == 0


def test_scenario_5_selective_propagation_in_multi_spec_mode() -> None:
    """Example 5: Multi-spec mode with selective propagation.

    Spec A: At 3/3 (fully verified)
    Spec B: At 2/3 (in verification)
    Spec C: At 0/3 (new work)
    Active Spec D: Works on implementation, changes files, returns DONE
    Result: Spec D -> 1/3, Spec A -> 2/3, Spec B -> 2/3, Spec C -> 0/3
    """
    state = _state(
        [3, 2, 0, 0],
        [Status.DONE.value, Status.DONE.value, None, None],
        current_index=3,
    )

    # Active spec D: DONE with file changes → 1/3
    # Spec A (3/3) should downgrade to 2/3
    # Spec B (2/3) remains unchanged
    # Spec C (0/3) remains unchanged
    _, _, state, done_count = handle_status(state, 3, Status.DONE, ["new-feature.py"], "hash-d")
    assert done_count == 1
    assert state.specs[0].done_count == 2  # A: 3/3 -> 2/3 downgrade
    assert state.specs[1].done_count == 2  # B: unchanged (not 3/3)
    assert state.specs[2].done_count == 0  # C: unchanged
    assert state.specs[3].done_count == 1  # D: DONE + changes -> 1


def test_multiple_3_of_three_specs_downgrade_on_change() -> None:
    """When one spec changes files, ALL other 3/3 specs downgrade to 2/3."""
    state = _state(
        [3, 3, 3, 0],
        [Status.DONE.value] * 3 + [None],
        current_index=3,
    )

    # Active spec D: DONE with file changes → 1/3
    # All three other 3/3 specs should downgrade to 2/3
    _, _, state, done_count = handle_status(state, 3, Status.DONE, ["feature.py"], "hash-d")
    assert done_count == 1
    assert state.specs[0].done_count == 2  # All three downgrade
    assert state.specs[1].done_count == 2
    assert state.specs[2].done_count == 2
    assert state.specs[3].done_count == 1


def test_non_done_with_changes_downgrades_other_3_of_three() -> None:
    """Non-DONE with changes resets current to 0 and downgrades other 3/3 specs."""
    state = _state(
        [3, 2],
        [Status.DONE.value, Status.CONTINUE.value],
        current_index=1,
    )

    # Spec B: CONTINUE with changes → 0/3
    # Spec A (3/3) should downgrade to 2/3
    _, _, state, done_count = handle_status(state, 1, Status.CONTINUE, ["feature.py"], "hash-b")
    assert done_count == 0
    assert state.specs[0].done_count == 2  # A: 3/3 -> 2/3 downgrade
    assert state.specs[1].done_count == 0  # B: CONTINUE + changes -> 0


def test_counter_starts_at_zero_for_new_specs() -> None:
    """Counter starts at 0/3 for brand new specs."""
    state = _state([0], [None], current_index=0)
    assert state.specs[0].done_count == 0


def test_counter_stays_at_three_when_already_complete() -> None:
    """Counter stays at 3/3 when already fully verified (no more work)."""
    state = _state([3], [Status.DONE.value], current_index=0)

    # Even with DONE and no changes, counter stays at 3
    _, _, updated, done_count = handle_status(state, 0, Status.DONE, [], "hash")
    assert done_count == 3
    assert updated.specs[0].done_count == 3


def test_multi_spec_propagation_preserves_in_progress_specs() -> None:
    """Multi-spec propagation preserves in-progress specs at 1/3 and 2/3."""
    state = _state(
        [3, 1, 2],
        [Status.DONE.value, Status.CONTINUE.value, Status.DONE.value],
        current_index=0,
    )

    # Spec A (current): DONE without changes → still 3/3 (no propagation for current)
    _, _, state, done_count = handle_status(state, 0, Status.DONE, [], "hash-a")
    assert done_count == 3
    assert state.specs[0].done_count == 3  # Current spec unchanged
    assert state.specs[1].done_count == 1  # B: preserved at 1/3
    assert state.specs[2].done_count == 2  # C: preserved at 2/3


def test_propagation_on_active_spec_with_no_changes() -> None:
    """When active spec has DONE without changes, no propagation occurs."""
    state = _state(
        [1, 3],
        [Status.DONE.value, Status.DONE.value],
        current_index=0,
    )

    # Spec A (current): DONE without changes → 2/3
    # No file changes, so no propagation to other specs
    _, _, state, done_count = handle_status(state, 0, Status.DONE, [], "hash-a")
    assert done_count == 2
    assert state.specs[0].done_count == 2  # A: increments
    assert state.specs[1].done_count == 3  # B: unchanged (no file changes)


def test_done_with_changes_only_downgrades_other_specs_not_current() -> None:
    """DONE with changes resets current to 1, not to 0."""
    state = _state([2], [Status.DONE.value], current_index=0)

    # DONE + changes should reset to 1/3, not 0/3
    _, _, state, done_count = handle_status(state, 0, Status.DONE, ["feature.py"], "hash")
    assert done_count == 1
    assert state.specs[0].done_count == 1


def test_non_done_with_no_changes_is_completely_stable() -> None:
    """Non-DONE without changes is a no-op - counter stays exactly the same."""
    for status in (Status.CONTINUE, Status.ROTATE):
        state = _state([1], [None], current_index=0)
        _, _, updated, done_count = handle_status(state, 0, status, [], "hash")
        assert done_count == 1
        assert updated.specs[0].done_count == 1

    state = _state([2], [None], current_index=0)
    _, _, updated, done_count = handle_status(state, 0, Status.ROTATE, [], "hash")
    assert done_count == 2
    assert updated.specs[0].done_count == 2

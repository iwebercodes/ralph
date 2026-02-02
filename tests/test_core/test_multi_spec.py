"""Tests for multi-spec support."""

from __future__ import annotations

from pathlib import Path

from ralph.core.agent import AgentResult
from ralph.core.loop import handle_status, run_loop
from ralph.core.pool import AgentPool
from ralph.core.specs import discover_specs, spec_hash, spec_resource_key
from ralph.core.state import (
    MultiSpecState,
    SpecProgress,
    Status,
    get_handoff_path,
    get_history_dir,
    read_guardrails,
    write_guardrails,
    write_handoff,
    write_history,
)


class RecordingAgent:
    """Agent that always signals CONTINUE and never exhausts."""

    def __init__(self, root: Path):
        self._root = root

    @property
    def name(self) -> str:
        return "Recorder"

    def is_available(self) -> bool:
        return True

    def invoke(
        self,
        prompt: str,
        timeout: int = 1800,
        output_file: Path | None = None,
        crash_patterns: list[str] | None = None,
    ) -> AgentResult:
        (self._root / ".ralph" / "status").write_text(Status.CONTINUE.value)
        return AgentResult("ok", 0, None)

    def is_exhausted(self, result: AgentResult) -> bool:
        return False


def test_spec_discovery_and_sorting(temp_project: Path) -> None:
    """Discover specs from all locations with prompt first and sorted paths."""
    (temp_project / "PROMPT.md").write_text("# Goal\n\nPrompt")
    (temp_project / ".ralph" / "specs" / "nested").mkdir(parents=True)
    (temp_project / "specs" / "v2").mkdir(parents=True)

    (temp_project / ".ralph" / "specs" / "nested" / "b.spec.md").write_text("B")
    (temp_project / "specs" / "a.spec.md").write_text("A")
    (temp_project / "specs" / "v2" / "c.spec.md").write_text("C")

    specs = discover_specs(temp_project)
    rel_paths = [spec.rel_posix for spec in specs]

    assert rel_paths[0] == "PROMPT.md"
    assert rel_paths == sorted(
        rel_paths, key=lambda p: (0, "000-prompt.spec.md") if p == "PROMPT.md" else (1, p)
    )
    assert any("/" in path for path in rel_paths if path != "PROMPT.md")


def test_spec_hashing_unique_for_paths() -> None:
    """Hashes differ for distinct spec paths and stay short."""
    hash_a = spec_hash("specs/api.spec.md")
    hash_b = spec_hash("specs/v2/api.spec.md")
    assert hash_a != hash_b
    assert len(hash_a) == 6
    assert len(hash_b) == 6


def test_spec_hash_normalizes_separators() -> None:
    """Hashing uses forward slashes regardless of input separators."""
    assert spec_hash("specs\\api.spec.md") == spec_hash("specs/api.spec.md")


def test_spec_resource_key_uses_name_and_hash() -> None:
    """Resource keys include base name and short hash."""
    key = spec_resource_key("specs/api.spec.md")
    assert key.startswith("api.spec-")
    assert len(key.split("-")[-1]) == 6


def test_round_robin_iteration_order(project_with_prompt: Path) -> None:
    """Specs rotate in sorted order across iterations."""
    (project_with_prompt / "specs").mkdir(exist_ok=True)
    (project_with_prompt / "specs" / "a.spec.md").write_text("# Goal\nA")
    (project_with_prompt / "specs" / "b.spec.md").write_text("# Goal\nB")

    agent = RecordingAgent(project_with_prompt)
    pool = AgentPool([agent])
    observed: list[str] = []

    def on_iteration_start(
        iteration: int, max_iter: int, done_count: int, agent_name: str, spec_path: str
    ) -> None:
        observed.append(spec_path)

    result = run_loop(
        max_iter=3,
        root=project_with_prompt,
        agent_pool=pool,
        on_iteration_start=on_iteration_start,
    )

    assert result.exit_code == 3
    assert observed == ["PROMPT.md", "specs/a.spec.md", "specs/b.spec.md"]


def test_per_spec_handoffs_and_history_isolation(initialized_project: Path) -> None:
    """Handoffs and history are stored per spec."""
    spec_a = "specs/a.spec.md"
    spec_b = "specs/b.spec.md"

    write_handoff("A handoff", initialized_project, spec_a)
    write_handoff("B handoff", initialized_project, spec_b)

    handoff_a = get_handoff_path(spec_a, initialized_project)
    handoff_b = get_handoff_path(spec_b, initialized_project)
    assert handoff_a.exists()
    assert handoff_b.exists()
    assert handoff_a.read_text(encoding="utf-8") == "A handoff"
    assert handoff_b.read_text(encoding="utf-8") == "B handoff"

    write_history(1, "Log A", initialized_project, spec_a)
    write_history(1, "Log B", initialized_project, spec_b)

    history_a = get_history_dir(initialized_project, spec_a)
    history_b = get_history_dir(initialized_project, spec_b)
    assert (history_a / "001.log").read_text(encoding="utf-8") == "Log A"
    assert (history_b / "001.log").read_text(encoding="utf-8") == "Log B"


def test_guardrails_shared_across_specs(initialized_project: Path) -> None:
    """Guardrails remain shared for all specs."""
    write_guardrails("# Guardrails\n- Shared rule", initialized_project)
    assert read_guardrails(initialized_project) == "# Guardrails\n- Shared rule"


def test_ensure_state_creates_spec_resources(initialized_project: Path) -> None:
    """Ensure per-spec handoff files and history directories are created."""
    from ralph.core.state import ensure_state, get_handoff_path, get_history_dir

    spec_paths = ["PROMPT.md", "specs/a.spec.md"]
    ensure_state(spec_paths, initialized_project)

    for spec_path in spec_paths:
        assert get_handoff_path(spec_path, initialized_project).exists()
        assert get_history_dir(initialized_project, spec_path).is_dir()


def test_counters_reset_on_files_changed() -> None:
    """Any file changes reset all spec counters."""
    state = MultiSpecState(
        version=1,
        iteration=1,
        status=Status.CONTINUE,
        current_index=0,
        specs=[
            SpecProgress(path="a.spec.md", done_count=2),
            SpecProgress(path="b.spec.md", done_count=1),
        ],
    )
    action, exit_code, updated, _ = handle_status(state, 0, Status.DONE, ["file.py"], "hash-a")
    assert action == "continue"
    assert exit_code is None
    assert all(spec.done_count == 0 for spec in updated.specs)


def test_completion_when_all_specs_reach_three() -> None:
    """Completion triggers once all specs hit 3/3."""
    state = MultiSpecState(
        version=1,
        iteration=1,
        status=Status.CONTINUE,
        current_index=0,
        specs=[
            SpecProgress(path="a.spec.md", done_count=2),
            SpecProgress(path="b.spec.md", done_count=3),
        ],
    )
    action, exit_code, _, done_count = handle_status(state, 0, Status.DONE, [], "hash-a")
    assert action == "exit"
    assert exit_code == 0
    assert done_count == 3


def test_spec_added_resets_all_counters(initialized_project: Path) -> None:
    """Adding a new spec file resets all counters."""
    from ralph.core.state import ensure_state, write_multi_state

    # Set up initial state with one spec and progress
    initial_state = MultiSpecState(
        version=1,
        iteration=5,
        status=Status.CONTINUE,
        current_index=0,
        specs=[SpecProgress(path="PROMPT.md", done_count=2)],
    )
    write_multi_state(initial_state, initialized_project)

    # Now discover with a new spec added
    new_spec_paths = ["PROMPT.md", "specs/new.spec.md"]
    result = ensure_state(new_spec_paths, initialized_project)

    # All counters should be reset to 0
    assert len(result.specs) == 2
    assert all(spec.done_count == 0 for spec in result.specs)
    assert result.iteration == 5  # iteration preserved


def test_spec_removed_resets_all_counters(initialized_project: Path) -> None:
    """Removing a spec file resets all counters."""
    from ralph.core.state import ensure_state, write_multi_state

    # Set up initial state with two specs
    initial_state = MultiSpecState(
        version=1,
        iteration=5,
        status=Status.CONTINUE,
        current_index=1,
        specs=[
            SpecProgress(path="PROMPT.md", done_count=2),
            SpecProgress(path="specs/old.spec.md", done_count=3),
        ],
    )
    write_multi_state(initial_state, initialized_project)

    # Now discover with one spec removed
    new_spec_paths = ["PROMPT.md"]
    result = ensure_state(new_spec_paths, initialized_project)

    # All counters should be reset to 0
    assert len(result.specs) == 1
    assert result.specs[0].done_count == 0
    assert result.current_index == 0  # reset since old index invalid


def test_unchanged_specs_preserve_progress(initialized_project: Path) -> None:
    """Unchanged spec list preserves all progress."""
    from ralph.core.state import ensure_state, write_multi_state

    # Set up initial state
    initial_state = MultiSpecState(
        version=1,
        iteration=5,
        status=Status.CONTINUE,
        current_index=1,
        specs=[
            SpecProgress(path="PROMPT.md", done_count=2),
            SpecProgress(path="specs/a.spec.md", done_count=1),
        ],
    )
    write_multi_state(initial_state, initialized_project)

    # Discover with same specs
    same_spec_paths = ["PROMPT.md", "specs/a.spec.md"]
    result = ensure_state(same_spec_paths, initialized_project)

    # Progress should be preserved
    assert result.specs[0].done_count == 2
    assert result.specs[1].done_count == 1
    assert result.current_index == 1


def test_last_status_persisted_in_state_json(initialized_project: Path) -> None:
    """last_status is saved to and loaded from state.json."""
    from ralph.core.state import read_multi_state, write_multi_state

    state = MultiSpecState(
        version=1,
        iteration=5,
        status=Status.CONTINUE,
        current_index=0,
        specs=[
            SpecProgress(
                path="a.spec.md", done_count=0, last_status="CONTINUE", last_hash="hash-a"
            ),
            SpecProgress(path="b.spec.md", done_count=3, last_status="DONE", last_hash="hash-b"),
            SpecProgress(path="c.spec.md", done_count=0, last_status=None, last_hash=None),
        ],
    )
    write_multi_state(state, initialized_project)

    loaded = read_multi_state(initialized_project)
    assert loaded is not None
    assert loaded.specs[0].last_status == "CONTINUE"
    assert loaded.specs[0].last_hash == "hash-a"
    assert loaded.specs[1].last_status == "DONE"
    assert loaded.specs[1].last_hash == "hash-b"
    assert loaded.specs[2].last_status is None
    assert loaded.specs[2].last_hash is None


def test_ensure_state_preserves_last_status(initialized_project: Path) -> None:
    """ensure_state preserves last_status when specs haven't changed."""
    from ralph.core.state import ensure_state, write_multi_state

    initial_state = MultiSpecState(
        version=1,
        iteration=5,
        status=Status.CONTINUE,
        current_index=0,
        specs=[
            SpecProgress(path="a.spec.md", done_count=0, last_status="CONTINUE"),
            SpecProgress(path="b.spec.md", done_count=3, last_status="DONE"),
        ],
    )
    write_multi_state(initial_state, initialized_project)

    result = ensure_state(["a.spec.md", "b.spec.md"], initialized_project)

    assert result.specs[0].last_status == "CONTINUE"
    assert result.specs[1].last_status == "DONE"


def test_ensure_state_clears_status_on_spec_content_change(initialized_project: Path) -> None:
    """Spec content changes reset last_status and done_count for that spec."""
    from ralph.core.specs import spec_content_hash
    from ralph.core.state import ensure_state, write_multi_state

    (initialized_project / "specs").mkdir(exist_ok=True)
    spec_path = initialized_project / "specs" / "a.spec.md"
    spec_path.write_text("# Goal\nOriginal")
    initial_hash = spec_content_hash(spec_path)
    spec_b_path = initialized_project / "specs" / "b.spec.md"
    spec_b_path.write_text("# Goal\nB")
    hash_b = spec_content_hash(spec_b_path)

    initial_state = MultiSpecState(
        version=1,
        iteration=5,
        status=Status.CONTINUE,
        current_index=0,
        specs=[
            SpecProgress(
                path="specs/a.spec.md",
                done_count=2,
                last_status="DONE",
                last_hash=initial_hash,
            ),
            SpecProgress(
                path="specs/b.spec.md",
                done_count=1,
                last_status="CONTINUE",
                last_hash=hash_b,
            ),
        ],
    )
    write_multi_state(initial_state, initialized_project)

    spec_path.write_text("# Goal\nModified")
    result = ensure_state(["specs/a.spec.md", "specs/b.spec.md"], initialized_project)

    assert result.specs[0].done_count == 0
    assert result.specs[0].last_status is None
    assert result.specs[0].last_hash == initial_hash
    assert result.specs[1].done_count == 0
    assert result.specs[1].last_status == "CONTINUE"
    assert result.specs[1].last_hash == hash_b


def test_ensure_state_preserves_spec_order_on_change(initialized_project: Path) -> None:
    """Spec discovery order is preserved even when spec content changes."""
    from ralph.core.specs import spec_content_hash
    from ralph.core.state import ensure_state, write_multi_state

    (initialized_project / "specs").mkdir(exist_ok=True)
    spec_a = initialized_project / "specs" / "a.spec.md"
    spec_b = initialized_project / "specs" / "b.spec.md"
    spec_a.write_text("# Goal\nA")
    spec_b.write_text("# Goal\nB")

    hash_a = spec_content_hash(spec_a)
    hash_b = spec_content_hash(spec_b)

    initial_state = MultiSpecState(
        version=1,
        iteration=5,
        status=Status.CONTINUE,
        current_index=0,
        specs=[
            SpecProgress(
                path="specs/a.spec.md", done_count=3, last_status="DONE", last_hash=hash_a
            ),
            SpecProgress(
                path="specs/b.spec.md", done_count=3, last_status="DONE", last_hash=hash_b
            ),
        ],
    )
    write_multi_state(initial_state, initialized_project)

    spec_b.write_text("# Goal\nB updated")
    result = ensure_state(["specs/a.spec.md", "specs/b.spec.md"], initialized_project)

    assert [spec.path for spec in result.specs] == ["specs/a.spec.md", "specs/b.spec.md"]


def test_ensure_state_clears_last_status_on_spec_change(initialized_project: Path) -> None:
    """ensure_state clears last_status when spec list changes."""
    from ralph.core.state import ensure_state, write_multi_state

    initial_state = MultiSpecState(
        version=1,
        iteration=5,
        status=Status.CONTINUE,
        current_index=0,
        specs=[
            SpecProgress(path="a.spec.md", done_count=2, last_status="CONTINUE"),
        ],
    )
    write_multi_state(initial_state, initialized_project)

    # Add a new spec
    result = ensure_state(["a.spec.md", "new.spec.md"], initialized_project)

    # All specs should have reset done_count and last_status
    assert result.specs[0].done_count == 0
    assert result.specs[0].last_status is None
    assert result.specs[1].done_count == 0
    assert result.specs[1].last_status is None


def test_handle_status_updates_last_status() -> None:
    """handle_status updates last_status after processing a spec."""
    state = MultiSpecState(
        version=1,
        iteration=1,
        status=Status.CONTINUE,
        current_index=0,
        specs=[
            SpecProgress(path="a.spec.md", done_count=0, last_status=None),
            SpecProgress(path="b.spec.md", done_count=0, last_status=None),
        ],
    )

    # Process first spec with DONE
    action, exit_code, updated, _ = handle_status(state, 0, Status.DONE, [], "hash-a")
    assert updated.specs[0].last_status == "DONE"
    assert updated.specs[0].last_hash == "hash-a"
    assert updated.specs[1].last_status is None  # Second spec unchanged

    # Process second spec with CONTINUE
    action, exit_code, updated2, _ = handle_status(updated, 1, Status.CONTINUE, [], "hash-b")
    assert updated2.specs[0].last_status == "DONE"
    assert updated2.specs[1].last_status == "CONTINUE"
    assert updated2.specs[1].last_hash == "hash-b"


def test_handle_status_preserves_last_status_on_reset() -> None:
    """When files change, last_status is preserved but done_count resets."""
    state = MultiSpecState(
        version=1,
        iteration=1,
        status=Status.CONTINUE,
        current_index=0,
        specs=[
            SpecProgress(path="a.spec.md", done_count=2, last_status="DONE"),
            SpecProgress(path="b.spec.md", done_count=1, last_status="CONTINUE"),
        ],
    )

    # Files changed - should reset done_count but preserve last_status
    action, exit_code, updated, _ = handle_status(state, 0, Status.DONE, ["file.py"], "hash-a")

    # done_count reset for all specs
    assert all(spec.done_count == 0 for spec in updated.specs)
    # last_status preserved for other specs, updated for current
    assert updated.specs[0].last_status == "DONE"  # Current spec updated
    assert updated.specs[0].last_hash == "hash-a"
    assert updated.specs[1].last_status == "CONTINUE"  # Other spec preserved


def test_reset_preserves_spec_states(initialized_project: Path) -> None:
    """Reset preserves spec states (last_status, last_hash, modified_files) but resets done."""
    import contextlib

    import typer

    from ralph.commands.reset import reset as reset_command
    from ralph.core.state import read_multi_state, write_multi_state

    # Set up state with specs that have last_status and done_count
    initial_state = MultiSpecState(
        version=1,
        iteration=5,
        status=Status.DONE,
        current_index=0,
        specs=[
            SpecProgress(
                path="a.spec.md",
                done_count=3,
                last_status="DONE",
                last_hash="hash-a",
                modified_files=True,
            ),
            SpecProgress(
                path="b.spec.md",
                done_count=1,
                last_status="CONTINUE",
                last_hash="hash-b",
                modified_files=False,
            ),
        ],
    )
    write_multi_state(initial_state, initialized_project)

    # Run reset
    with contextlib.suppress(typer.Exit):
        reset_command()

    # Check state after reset - spec states should be preserved but done_count reset
    state = read_multi_state(initialized_project)
    assert state is not None
    assert state.iteration == 0
    assert len(state.specs) == 2

    # last_status and last_hash should be preserved
    assert state.specs[0].last_status == "DONE"
    assert state.specs[0].last_hash == "hash-a"
    assert state.specs[0].modified_files is True
    assert state.specs[1].last_status == "CONTINUE"
    assert state.specs[1].last_hash == "hash-b"
    assert state.specs[1].modified_files is False

    # done_count should be reset to 0
    assert all(spec.done_count == 0 for spec in state.specs)


def test_spec_priority_key_new_first() -> None:
    """New specs (no last_status) have highest priority."""
    from ralph.core.specs import spec_priority_key

    # New spec (no last_status)
    key_new = spec_priority_key("a.spec.md", None, None, "hash-a")
    # Non-DONE spec
    key_continue = spec_priority_key("b.spec.md", "CONTINUE", "hash-b", "hash-b")
    # DONE spec
    key_done = spec_priority_key("c.spec.md", "DONE", "hash-c", "hash-c")

    assert key_new < key_continue < key_done


def test_spec_priority_key_modified_first() -> None:
    """Modified specs (hash changed) have highest priority."""
    from ralph.core.specs import spec_priority_key

    # Modified spec (hash changed)
    key_modified = spec_priority_key("a.spec.md", "DONE", "old-hash", "new-hash")
    # Non-modified DONE spec
    key_done = spec_priority_key("b.spec.md", "DONE", "hash-b", "hash-b")

    assert key_modified < key_done


def test_spec_priority_key_alphabetical_within_tier() -> None:
    """Specs with same priority tier are sorted alphabetically."""
    from ralph.core.specs import spec_priority_key

    # Both are new
    key_a = spec_priority_key("a.spec.md", None, None, "hash-a")
    key_b = spec_priority_key("b.spec.md", None, None, "hash-b")

    # Same tier (0), sorted by path
    assert key_a[0] == key_b[0] == 0
    assert key_a < key_b  # "a.spec.md" < "b.spec.md"


def test_sort_specs_by_state_prioritizes_new(initialized_project: Path) -> None:
    """New specs (no saved state) are sorted before DONE specs."""
    from ralph.core.specs import Spec, sort_specs_by_state, spec_content_hash

    (initialized_project / "specs").mkdir(exist_ok=True)
    (initialized_project / "specs" / "a.spec.md").write_text("# A")
    (initialized_project / "specs" / "b.spec.md").write_text("# B")
    (initialized_project / "specs" / "c.spec.md").write_text("# C")

    # Get actual content hashes
    hash_b = spec_content_hash(initialized_project / "specs" / "b.spec.md")

    specs = [
        Spec(
            path=initialized_project / "specs" / "a.spec.md",
            rel_posix="specs/a.spec.md",
            is_prompt=False,
        ),
        Spec(
            path=initialized_project / "specs" / "b.spec.md",
            rel_posix="specs/b.spec.md",
            is_prompt=False,
        ),
        Spec(
            path=initialized_project / "specs" / "c.spec.md",
            rel_posix="specs/c.spec.md",
            is_prompt=False,
        ),
    ]

    # b is DONE with matching hash (no file changes), a and c are new (not in spec_states)
    spec_states: dict[str, tuple[str | None, str | None, bool]] = {
        "specs/b.spec.md": ("DONE", hash_b, False),
    }

    sorted_specs = sort_specs_by_state(specs, spec_states, initialized_project)
    sorted_paths = [s.rel_posix for s in sorted_specs]

    # New specs (a, c) should come before DONE spec (b)
    assert sorted_paths == ["specs/a.spec.md", "specs/c.spec.md", "specs/b.spec.md"]


def test_sort_specs_by_state_prioritizes_non_done(initialized_project: Path) -> None:
    """Non-DONE specs are sorted before DONE specs."""
    from ralph.core.specs import Spec, sort_specs_by_state, spec_content_hash

    (initialized_project / "specs").mkdir(exist_ok=True)
    (initialized_project / "specs" / "a.spec.md").write_text("# A")
    (initialized_project / "specs" / "b.spec.md").write_text("# B")

    # Get actual content hashes
    hash_a = spec_content_hash(initialized_project / "specs" / "a.spec.md")
    hash_b = spec_content_hash(initialized_project / "specs" / "b.spec.md")

    specs = [
        Spec(
            path=initialized_project / "specs" / "a.spec.md",
            rel_posix="specs/a.spec.md",
            is_prompt=False,
        ),
        Spec(
            path=initialized_project / "specs" / "b.spec.md",
            rel_posix="specs/b.spec.md",
            is_prompt=False,
        ),
    ]

    # b is CONTINUE (non-DONE), a is DONE - both with matching hashes
    spec_states: dict[str, tuple[str | None, str | None, bool]] = {
        "specs/a.spec.md": ("DONE", hash_a, False),
        "specs/b.spec.md": ("CONTINUE", hash_b, False),
    }

    sorted_specs = sort_specs_by_state(specs, spec_states, initialized_project)
    sorted_paths = [s.rel_posix for s in sorted_specs]

    # Non-DONE (b) should come before DONE (a)
    assert sorted_paths == ["specs/b.spec.md", "specs/a.spec.md"]


def test_loop_sorts_by_priority_on_restart(project_with_prompt: Path) -> None:
    """Loop re-sorts by priority on restart, starting with highest priority spec."""
    from ralph.core.specs import spec_content_hash
    from ralph.core.state import write_multi_state

    (project_with_prompt / "specs").mkdir(exist_ok=True)
    (project_with_prompt / "specs" / "a.spec.md").write_text("# Goal\nA")
    (project_with_prompt / "specs" / "b.spec.md").write_text("# Goal\nB")

    # Get actual content hashes
    hash_p = spec_content_hash(project_with_prompt / "PROMPT.md")
    hash_a = spec_content_hash(project_with_prompt / "specs" / "a.spec.md")
    hash_b = spec_content_hash(project_with_prompt / "specs" / "b.spec.md")

    # Set up state where b.spec.md is CONTINUE (non-DONE) and others are DONE.
    # On restart, run_loop should re-sort by priority, putting b first.
    initial_state = MultiSpecState(
        version=1,
        iteration=0,
        status=Status.IDLE,
        current_index=0,
        specs=[
            SpecProgress(path="PROMPT.md", done_count=2, last_status="DONE", last_hash=hash_p),
            SpecProgress(
                path="specs/a.spec.md", done_count=2, last_status="DONE", last_hash=hash_a
            ),
            SpecProgress(
                path="specs/b.spec.md", done_count=0, last_status="CONTINUE", last_hash=hash_b
            ),
        ],
    )
    write_multi_state(initial_state, project_with_prompt)

    agent = RecordingAgent(project_with_prompt)
    pool = AgentPool([agent])
    observed: list[str] = []

    def on_iteration_start(
        iteration: int, max_iter: int, done_count: int, agent_name: str, spec_path: str
    ) -> None:
        observed.append(spec_path)

    result = run_loop(
        max_iter=1,
        root=project_with_prompt,
        agent_pool=pool,
        on_iteration_start=on_iteration_start,
    )

    assert result.exit_code == 3
    # Should start with b.spec.md because it's CONTINUE (higher priority than DONE)
    assert observed == ["specs/b.spec.md"]


def test_state_persists_across_restarts(project_with_prompt: Path) -> None:
    """Spec state (last_status, last_hash) persists across ralph restarts."""
    from ralph.core.state import read_multi_state, write_multi_state

    # Write initial state
    initial_state = MultiSpecState(
        version=1,
        iteration=5,
        status=Status.CONTINUE,
        current_index=0,
        specs=[
            SpecProgress(
                path="PROMPT.md", done_count=2, last_status="CONTINUE", last_hash="hash-p"
            ),
        ],
    )
    write_multi_state(initial_state, project_with_prompt)

    # Read state (simulating a restart)
    loaded_state = read_multi_state(project_with_prompt)

    assert loaded_state is not None
    assert loaded_state.iteration == 5
    assert loaded_state.specs[0].last_status == "CONTINUE"
    assert loaded_state.specs[0].last_hash == "hash-p"
    assert loaded_state.specs[0].done_count == 2


# =============================================================================
# Smart Spec Sorting Tests
# =============================================================================


def test_spec_priority_key_five_tiers() -> None:
    """Verify all 5 priority tiers are correctly ordered."""
    from ralph.core.specs import spec_priority_key

    # Tier 0: New spec (no last_status)
    key_new = spec_priority_key("spec.md", None, None, "hash")
    # Tier 1: Modified spec (hash changed)
    key_modified = spec_priority_key("spec.md", "DONE", "old-hash", "new-hash")
    # Tier 2: Non-DONE (e.g., CONTINUE)
    key_non_done = spec_priority_key("spec.md", "CONTINUE", "hash", "hash")
    # Tier 3: DONE with modified_files=True
    key_done_modified = spec_priority_key("spec.md", "DONE", "hash", "hash", modified_files=True)
    # Tier 4: DONE without modified_files
    key_done_clean = spec_priority_key("spec.md", "DONE", "hash", "hash", modified_files=False)

    # Verify tier ordering
    assert key_new[0] == 0
    assert key_modified[0] == 1
    assert key_non_done[0] == 2
    assert key_done_modified[0] == 3
    assert key_done_clean[0] == 4

    # Verify full ordering
    assert key_new < key_modified < key_non_done < key_done_modified < key_done_clean


def test_sort_specs_by_state_done_with_changes_before_clean(initialized_project: Path) -> None:
    """DONE specs that modified files come before DONE specs that didn't."""
    from ralph.core.specs import Spec, sort_specs_by_state, spec_content_hash

    (initialized_project / "specs").mkdir(exist_ok=True)
    (initialized_project / "specs" / "clean.spec.md").write_text("# Clean")
    (initialized_project / "specs" / "modified.spec.md").write_text("# Modified")

    hash_clean = spec_content_hash(initialized_project / "specs" / "clean.spec.md")
    hash_modified = spec_content_hash(initialized_project / "specs" / "modified.spec.md")

    specs = [
        Spec(
            path=initialized_project / "specs" / "clean.spec.md",
            rel_posix="specs/clean.spec.md",
            is_prompt=False,
        ),
        Spec(
            path=initialized_project / "specs" / "modified.spec.md",
            rel_posix="specs/modified.spec.md",
            is_prompt=False,
        ),
    ]

    # Both DONE, but modified.spec.md had file changes
    spec_states: dict[str, tuple[str | None, str | None, bool]] = {
        "specs/clean.spec.md": ("DONE", hash_clean, False),  # No file changes
        "specs/modified.spec.md": ("DONE", hash_modified, True),  # Had file changes
    }

    sorted_specs = sort_specs_by_state(specs, spec_states, initialized_project)
    sorted_paths = [s.rel_posix for s in sorted_specs]

    # DONE with file changes should come before DONE without
    assert sorted_paths == ["specs/modified.spec.md", "specs/clean.spec.md"]


def test_handle_status_sets_modified_files_on_done() -> None:
    """handle_status sets modified_files based on whether files changed."""
    from ralph.core.loop import handle_status

    # No file changes - modified_files should be False
    state = MultiSpecState(
        version=1,
        iteration=1,
        status=Status.CONTINUE,
        current_index=0,
        specs=[SpecProgress(path="a.spec.md", done_count=0)],
    )
    _, _, updated, _ = handle_status(state, 0, Status.DONE, [], "hash-a")
    assert updated.specs[0].modified_files is False

    # With file changes - modified_files should be True
    state2 = MultiSpecState(
        version=1,
        iteration=1,
        status=Status.CONTINUE,
        current_index=0,
        specs=[SpecProgress(path="a.spec.md", done_count=0)],
    )
    _, _, updated2, _ = handle_status(state2, 0, Status.DONE, ["file.py"], "hash-a")
    assert updated2.specs[0].modified_files is True


def test_handle_status_sets_modified_files_on_non_done() -> None:
    """handle_status sets modified_files for non-DONE statuses too."""
    from ralph.core.loop import handle_status

    state = MultiSpecState(
        version=1,
        iteration=1,
        status=Status.CONTINUE,
        current_index=0,
        specs=[SpecProgress(path="a.spec.md", done_count=0)],
    )

    # CONTINUE with file changes
    _, _, updated, _ = handle_status(state, 0, Status.CONTINUE, ["file.py"], "hash-a")
    assert updated.specs[0].modified_files is True
    assert updated.specs[0].last_status == "CONTINUE"


def test_modified_files_persisted_in_state_json(initialized_project: Path) -> None:
    """modified_files is saved to and loaded from state.json."""
    from ralph.core.state import read_multi_state, write_multi_state

    state = MultiSpecState(
        version=1,
        iteration=5,
        status=Status.CONTINUE,
        current_index=0,
        specs=[
            SpecProgress(path="a.spec.md", done_count=0, last_status="DONE", modified_files=True),
            SpecProgress(path="b.spec.md", done_count=0, last_status="DONE", modified_files=False),
        ],
    )
    write_multi_state(state, initialized_project)

    loaded = read_multi_state(initialized_project)
    assert loaded is not None
    assert loaded.specs[0].modified_files is True
    assert loaded.specs[1].modified_files is False


def test_ensure_state_preserves_order_when_specs_unchanged(initialized_project: Path) -> None:
    """ensure_state preserves spec order when spec set hasn't changed."""
    from ralph.core.state import ensure_state, write_multi_state

    # Set up state with specific order (c, a, b - NOT alphabetical)
    initial_state = MultiSpecState(
        version=1,
        iteration=5,
        status=Status.CONTINUE,
        current_index=0,
        specs=[
            SpecProgress(path="specs/c.spec.md", done_count=0, last_status="CONTINUE"),
            SpecProgress(path="specs/a.spec.md", done_count=1, last_status="DONE"),
            SpecProgress(path="specs/b.spec.md", done_count=2, last_status="DONE"),
        ],
    )
    write_multi_state(initial_state, initialized_project)

    # Call ensure_state with specs in ALPHABETICAL order
    result = ensure_state(
        ["specs/a.spec.md", "specs/b.spec.md", "specs/c.spec.md"], initialized_project
    )

    # Order should be preserved from existing state (c, a, b), not the input order
    assert [spec.path for spec in result.specs] == [
        "specs/c.spec.md",
        "specs/a.spec.md",
        "specs/b.spec.md",
    ]


def test_ensure_state_uses_new_order_when_specs_change(initialized_project: Path) -> None:
    """ensure_state uses the new order when spec set changes."""
    from ralph.core.state import ensure_state, write_multi_state

    # Set up state with one spec
    initial_state = MultiSpecState(
        version=1,
        iteration=5,
        status=Status.CONTINUE,
        current_index=0,
        specs=[
            SpecProgress(path="specs/b.spec.md", done_count=2, last_status="DONE"),
        ],
    )
    write_multi_state(initial_state, initialized_project)

    # Call ensure_state with a NEW spec added (different set)
    result = ensure_state(["specs/a.spec.md", "specs/b.spec.md"], initialized_project)

    # Order should come from the input (a, b), not preserved from old state
    assert [spec.path for spec in result.specs] == [
        "specs/a.spec.md",
        "specs/b.spec.md",
    ]


def test_run_loop_sorts_specs_by_priority(project_with_prompt: Path) -> None:
    """run_loop sorts specs by priority at the start of a run."""
    from ralph.core.specs import spec_content_hash
    from ralph.core.state import write_multi_state

    (project_with_prompt / "specs").mkdir(exist_ok=True)
    (project_with_prompt / "specs" / "a.spec.md").write_text("# Goal\nA")
    (project_with_prompt / "specs" / "b.spec.md").write_text("# Goal\nB")

    # Get actual content hashes
    hash_p = spec_content_hash(project_with_prompt / "PROMPT.md")
    hash_a = spec_content_hash(project_with_prompt / "specs" / "a.spec.md")
    hash_b = spec_content_hash(project_with_prompt / "specs" / "b.spec.md")

    # Set up state where b.spec.md is CONTINUE (non-DONE) and others are DONE
    # Priority should be: b (non-DONE), then PROMPT (DONE), then a (DONE)
    initial_state = MultiSpecState(
        version=1,
        iteration=0,
        status=Status.IDLE,
        current_index=0,
        specs=[
            SpecProgress(path="PROMPT.md", done_count=0, last_status="DONE", last_hash=hash_p),
            SpecProgress(
                path="specs/a.spec.md", done_count=0, last_status="DONE", last_hash=hash_a
            ),
            SpecProgress(
                path="specs/b.spec.md", done_count=0, last_status="CONTINUE", last_hash=hash_b
            ),
        ],
    )
    write_multi_state(initial_state, project_with_prompt)

    agent = RecordingAgent(project_with_prompt)
    pool = AgentPool([agent])
    observed: list[str] = []

    def on_iteration_start(
        iteration: int, max_iter: int, done_count: int, agent_name: str, spec_path: str
    ) -> None:
        observed.append(spec_path)

    result = run_loop(
        max_iter=3,
        root=project_with_prompt,
        agent_pool=pool,
        on_iteration_start=on_iteration_start,
    )

    assert result.exit_code == 3
    # First iteration should be b (non-DONE, highest priority among existing)
    # Then PROMPT.md (DONE), then a.spec.md (DONE)
    assert observed[0] == "specs/b.spec.md"


def test_run_loop_maintains_order_during_run(project_with_prompt: Path) -> None:
    """run_loop maintains spec order during a run (round-robin)."""
    from ralph.core.specs import spec_content_hash
    from ralph.core.state import write_multi_state

    (project_with_prompt / "specs").mkdir(exist_ok=True)
    (project_with_prompt / "specs" / "a.spec.md").write_text("# Goal\nA")
    (project_with_prompt / "specs" / "b.spec.md").write_text("# Goal\nB")

    # Get actual content hashes
    hash_p = spec_content_hash(project_with_prompt / "PROMPT.md")
    hash_a = spec_content_hash(project_with_prompt / "specs" / "a.spec.md")
    hash_b = spec_content_hash(project_with_prompt / "specs" / "b.spec.md")

    # Set up state with non-alphabetical order that should be maintained
    # b is CONTINUE (will be sorted first), PROMPT is DONE, a is DONE
    initial_state = MultiSpecState(
        version=1,
        iteration=0,
        status=Status.IDLE,
        current_index=0,
        specs=[
            SpecProgress(
                path="specs/b.spec.md", done_count=0, last_status="CONTINUE", last_hash=hash_b
            ),
            SpecProgress(path="PROMPT.md", done_count=0, last_status="DONE", last_hash=hash_p),
            SpecProgress(
                path="specs/a.spec.md", done_count=0, last_status="DONE", last_hash=hash_a
            ),
        ],
    )
    write_multi_state(initial_state, project_with_prompt)

    agent = RecordingAgent(project_with_prompt)
    pool = AgentPool([agent])
    observed: list[str] = []

    def on_iteration_start(
        iteration: int, max_iter: int, done_count: int, agent_name: str, spec_path: str
    ) -> None:
        observed.append(spec_path)

    result = run_loop(
        max_iter=6,
        root=project_with_prompt,
        agent_pool=pool,
        on_iteration_start=on_iteration_start,
    )

    assert result.exit_code == 3
    # Should maintain round-robin in order: b, PROMPT, a, b, PROMPT, a
    assert observed == [
        "specs/b.spec.md",
        "PROMPT.md",
        "specs/a.spec.md",
        "specs/b.spec.md",
        "PROMPT.md",
        "specs/a.spec.md",
    ]

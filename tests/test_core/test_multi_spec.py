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
    action, exit_code, updated, _ = handle_status(state, 0, Status.DONE, ["file.py"])
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
    action, exit_code, _, done_count = handle_status(state, 0, Status.DONE, [])
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

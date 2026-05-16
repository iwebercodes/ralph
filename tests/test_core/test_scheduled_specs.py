"""Tests for system specs (.every-[n].spec.md): periodic, stateless tasks."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ralph.core.agent import AgentResult
from ralph.core.loop import (
    _all_specs_done,
    run_loop,
)
from ralph.core.pool import AgentPool
from ralph.core.specs import (
    discover_specs,
    is_system_spec,
    parse_every_n,
    split_specs,
    system_spec_eligible,
)
from ralph.core.state import (
    MultiSpecState,
    SpecProgress,
    Status,
    ensure_state,
    read_multi_state,
    write_multi_state,
)

IS_WINDOWS = sys.platform == "win32"


# =============================================================================
# parse_every_n Tests
# =============================================================================


class TestParseEveryN:
    """Tests for the parse_every_n function."""

    def test_simple_every_n(self) -> None:
        """Extract n from .every-[n].spec.md pattern."""
        assert parse_every_n("cleanup.every-3.spec.md") == 3
        assert parse_every_n("consolidate-docs.every-5.spec.md") == 5
        assert parse_every_n("check-format-subpages.every-10.spec.md") == 10

    def test_multiple_every_n_uses_last(self) -> None:
        """If multiple .every-[n] segments exist, use the last one."""
        assert parse_every_n("a.every-2.b.every-3.spec.md") == 3
        assert parse_every_n("x.every-1.y.every-7.z.every-4.spec.md") == 4

    def test_no_every_n_pattern(self) -> None:
        """Regular specs without .every-[n] return 1."""
        assert parse_every_n("normal.spec.md") == 1
        assert parse_every_n("my.every.spec.md") == 1
        assert parse_every_n("specs/cleanup.spec.md") == 1

    def test_invalid_every_n(self) -> None:
        """Invalid patterns return 1."""
        assert parse_every_n(".every-.spec.md") == 1
        assert parse_every_n(".every-0.spec.md") == 1
        assert parse_every_n(".every-abc.spec.md") == 1

    def test_every_1_returns_1(self) -> None:
        """.every-1 behaves like a regular spec."""
        assert parse_every_n("spec.every-1.spec.md") == 1

    def test_with_subdirectory_path(self) -> None:
        """Works with paths containing subdirectories."""
        assert parse_every_n(".ralph/specs/cleanup.every-3.spec.md") == 3
        assert parse_every_n("specs/nested/deep/cleanup.every-5.spec.md") == 5

    def test_with_windows_separators(self) -> None:
        """Works with Windows-style path separators."""
        assert parse_every_n("specs\\cleanup.every-3.spec.md") == 3


# =============================================================================
# is_system_spec Tests
# =============================================================================


class TestIsSystemSpec:
    """Tests for is_system_spec."""

    def test_system_spec_with_n_gt_1(self) -> None:
        assert is_system_spec("cleanup.every-3.spec.md") is True
        assert is_system_spec("a.every-10.spec.md") is True

    def test_regular_spec_returns_false(self) -> None:
        assert is_system_spec("normal.spec.md") is False
        assert is_system_spec("PROMPT.md") is False

    def test_every_1_is_regular(self) -> None:
        assert is_system_spec("spec.every-1.spec.md") is False

    def test_every_0_is_regular(self) -> None:
        assert is_system_spec("spec.every-0.spec.md") is False

    def test_every_abc_is_regular(self) -> None:
        assert is_system_spec("spec.every-abc.spec.md") is False


# =============================================================================
# system_spec_eligible Tests
# =============================================================================


class TestSystemSpecEligible:
    """Tests for system_spec_eligible — fires when iteration % n == 0."""

    def test_every_3_runs_on_multiples_of_3(self) -> None:
        for i in range(1, 15):
            expected = i % 3 == 0
            assert system_spec_eligible("a.every-3.spec.md", i) == expected

    def test_every_5_runs_on_multiples_of_5(self) -> None:
        for i in range(1, 20):
            expected = i % 5 == 0
            assert system_spec_eligible("a.every-5.spec.md", i) == expected

    def test_regular_spec_never_eligible_as_system(self) -> None:
        for i in range(1, 20):
            assert system_spec_eligible("normal.spec.md", i) is False


# =============================================================================
# split_specs Tests
# =============================================================================


class TestSplitSpecs:
    """Tests for split_specs — partitioning into regular + system."""

    def test_splits_regular_and_system(self, temp_project: Path) -> None:
        (temp_project / "specs").mkdir(exist_ok=True)
        (temp_project / "PROMPT.md").write_text("# Goal\nP")
        (temp_project / "specs" / "normal.spec.md").write_text("# Goal\nN")
        (temp_project / "specs" / "cleanup.every-3.spec.md").write_text("# Goal\nC")

        specs = discover_specs(temp_project)
        regular, system = split_specs(specs)
        regular_paths = {s.rel_posix for s in regular}
        system_paths = {s.rel_posix for s in system}

        assert "PROMPT.md" in regular_paths
        assert "specs/normal.spec.md" in regular_paths
        assert "specs/cleanup.every-3.spec.md" in system_paths
        assert "specs/cleanup.every-3.spec.md" not in regular_paths

    def test_system_specs_sorted_alphabetically(self, temp_project: Path) -> None:
        (temp_project / "specs").mkdir(exist_ok=True)
        (temp_project / "specs" / "z.every-2.spec.md").write_text("# Goal\nZ")
        (temp_project / "specs" / "a.every-2.spec.md").write_text("# Goal\nA")
        (temp_project / "specs" / "m.every-2.spec.md").write_text("# Goal\nM")
        # Plus one regular spec to satisfy run_loop's exit-when-no-regulars check
        (temp_project / "specs" / "regular.spec.md").write_text("# Goal\nR")

        specs = discover_specs(temp_project)
        _, system = split_specs(specs)
        assert [s.rel_posix for s in system] == [
            "specs/a.every-2.spec.md",
            "specs/m.every-2.spec.md",
            "specs/z.every-2.spec.md",
        ]


# =============================================================================
# State Persistence: System specs are NOT in state
# =============================================================================


class TestSystemSpecsAreStateless:
    """System specs MUST NOT have entries in state.json."""

    def test_system_spec_not_in_state(self, initialized_project: Path) -> None:
        (initialized_project / "specs").mkdir(exist_ok=True)
        (initialized_project / "specs" / "regular.spec.md").write_text("# Goal\nR")
        (initialized_project / "specs" / "cleanup.every-3.spec.md").write_text("# Goal\nC")

        state = ensure_state(
            ["specs/regular.spec.md", "specs/cleanup.every-3.spec.md"], initialized_project
        )
        spec_paths = {s.path for s in state.specs}
        assert "specs/regular.spec.md" in spec_paths
        assert "specs/cleanup.every-3.spec.md" not in spec_paths

    def test_renaming_regular_to_system_drops_entry(self, initialized_project: Path) -> None:
        """A spec previously tracked as regular is removed from state when renamed."""
        (initialized_project / "specs").mkdir(exist_ok=True)
        # First: track as a regular spec
        (initialized_project / "specs" / "foo.spec.md").write_text("# Goal\nF")
        state = ensure_state(["specs/foo.spec.md"], initialized_project)
        assert any(s.path == "specs/foo.spec.md" for s in state.specs)

        # Now rename in state.json (simulate stale entry pointing at the new path)
        old_state = json.loads(
            (initialized_project / ".ralph" / "state.json").read_text(encoding="utf-8")
        )
        old_state["specs"] = [{"path": "specs/foo.every-3.spec.md", "done_count": 2}]
        (initialized_project / ".ralph" / "state.json").write_text(
            json.dumps(old_state), encoding="utf-8"
        )
        (initialized_project / "specs" / "foo.every-3.spec.md").write_text("# Goal\nF3")

        state = ensure_state(["specs/foo.every-3.spec.md"], initialized_project)
        # The system-spec entry must be dropped from state.specs.
        assert not any(s.path == "specs/foo.every-3.spec.md" for s in state.specs)

    def test_renaming_system_to_regular_creates_fresh_entry(
        self, initialized_project: Path
    ) -> None:
        """A spec renamed from system to regular gets a fresh state entry."""
        (initialized_project / "specs").mkdir(exist_ok=True)
        (initialized_project / "specs" / "foo.spec.md").write_text("# Goal\nF")
        state = ensure_state(["specs/foo.spec.md"], initialized_project)
        entry = next(s for s in state.specs if s.path == "specs/foo.spec.md")
        assert entry.done_count == 0
        assert entry.last_status is None

    def test_state_json_has_no_every_n_field(self, initialized_project: Path) -> None:
        """state.json should not serialize every_n (the field no longer exists)."""
        (initialized_project / "specs").mkdir(exist_ok=True)
        (initialized_project / "specs" / "a.spec.md").write_text("# Goal\nA")
        ensure_state(["specs/a.spec.md"], initialized_project)
        raw = json.loads(
            (initialized_project / ".ralph" / "state.json").read_text(encoding="utf-8")
        )
        for spec in raw["specs"]:
            assert "every_n" not in spec


# =============================================================================
# _all_specs_done
# =============================================================================


class TestAllSpecsDone:
    """Tests for _all_specs_done — considers only regular specs."""

    def test_all_done_true(self) -> None:
        state = MultiSpecState(
            version=1,
            iteration=5,
            status=Status.CONTINUE,
            current_index=0,
            specs=[
                SpecProgress(path="a.spec.md", done_count=3),
                SpecProgress(path="b.spec.md", done_count=3),
            ],
        )
        assert _all_specs_done(state) is True

    def test_all_done_false_when_pending(self) -> None:
        state = MultiSpecState(
            version=1,
            iteration=5,
            status=Status.CONTINUE,
            current_index=0,
            specs=[
                SpecProgress(path="a.spec.md", done_count=3),
                SpecProgress(path="b.spec.md", done_count=2),
            ],
        )
        assert _all_specs_done(state) is False

    def test_all_done_with_empty_state(self) -> None:
        state = MultiSpecState(
            version=1, iteration=0, status=Status.IDLE, current_index=0, specs=[]
        )
        # Vacuously true; the loop's exit logic separately treats "no regulars"
        # as exit-0.
        assert _all_specs_done(state) is True


# =============================================================================
# Mock agents
# =============================================================================


class _RecordingAgent:
    """Agent that records each (iteration, spec_path) invocation."""

    name = "Recorder"

    def __init__(self, root: Path) -> None:
        self._root = root
        # behaviors keyed by spec_path → (status, make_changes)
        self.behaviors: dict[str, tuple[str, bool]] = {}
        self.default_behavior: tuple[str, bool] = ("DONE", False)
        self.invocations: list[str] = []
        self._change_seq = 0

    def is_available(self) -> bool:
        return True

    def is_exhausted(self, result: AgentResult) -> bool:
        return False

    def exhaustion_reason(self, result: AgentResult) -> str | None:
        return None

    def invoke(
        self,
        prompt: str,
        timeout: int | None = 1800,
        output_file: Path | None = None,
        crash_patterns: list[str] | None = None,
    ) -> AgentResult:
        spec_path = ""
        for line in prompt.splitlines():
            stripped = line.strip()
            if stripped.startswith("Spec file:"):
                spec_path = stripped.split(":", 1)[1].strip()
                break
            if stripped.startswith("System spec file:"):
                spec_path = stripped.split(":", 1)[1].strip()
                break
        self.invocations.append(spec_path)
        status, changes = self.behaviors.get(spec_path, self.default_behavior)
        (self._root / ".ralph" / "status").write_text(status)
        if changes:
            self._change_seq += 1
            (self._root / "test_output.txt").write_text(
                f"changed by {spec_path} at {self._change_seq}"
            )
        return AgentResult("ok", 0, None)


# =============================================================================
# Discovery
# =============================================================================


class TestSpecDiscovery:
    """Tests for discovery of system spec files."""

    def test_discovers_every_n_specs(self, temp_project: Path) -> None:
        (temp_project / "specs").mkdir(exist_ok=True)
        (temp_project / "PROMPT.md").write_text("# Goal\nPrompt")
        (temp_project / "specs" / "cleanup.every-3.spec.md").write_text("# Goal\nCleanup")
        (temp_project / "specs" / "normal.spec.md").write_text("# Goal\nNormal")

        specs = discover_specs(temp_project)
        rel_paths = [spec.rel_posix for spec in specs]

        assert "PROMPT.md" in rel_paths
        assert "specs/cleanup.every-3.spec.md" in rel_paths
        assert "specs/normal.spec.md" in rel_paths

    def test_every_n_in_ralph_specs_directory(self, temp_project: Path) -> None:
        (temp_project / ".ralph" / "specs").mkdir(parents=True)
        (temp_project / ".ralph" / "specs" / "format.every-4.spec.md").write_text("# Goal\nF")

        specs = discover_specs(temp_project)
        rel_paths = [spec.rel_posix for spec in specs]
        assert ".ralph/specs/format.every-4.spec.md" in rel_paths

    def test_invalid_every_n_treated_as_regular(self, temp_project: Path) -> None:
        (temp_project / "specs").mkdir(exist_ok=True)
        (temp_project / "specs" / "my.every.spec.md").write_text("# Goal\nMy")

        specs = discover_specs(temp_project)
        rel_paths = [spec.rel_posix for spec in specs]
        assert "specs/my.every.spec.md" in rel_paths
        # Confirmed as regular: not a system spec
        assert not is_system_spec("specs/my.every.spec.md")


# =============================================================================
# Run-loop behavior: system phase runs BEFORE the regular phase
# =============================================================================


class TestSystemRunsBeforeRegular:
    """The system phase fires before the regular phase within the same iteration."""

    def test_system_runs_on_period_iterations(self, initialized_project: Path) -> None:
        """System spec fires when iteration % n == 0; regular runs every iter."""
        (initialized_project / "specs").mkdir(exist_ok=True)
        (initialized_project / "specs" / "regular.spec.md").write_text("# Goal\nR")
        (initialized_project / "specs" / "cleanup.every-3.spec.md").write_text("# Goal\nC")

        agent = _RecordingAgent(initialized_project)
        # Regular returns CONTINUE every time so it never finishes within max_iter.
        agent.default_behavior = ("CONTINUE", False)
        observed_regular: list[tuple[int, str]] = []
        observed_system: list[tuple[int, str]] = []

        def on_iteration_start(
            iteration: int, max_iter: int, done_count: int, agent_name: str, spec_path: str
        ) -> None:
            observed_regular.append((iteration, spec_path))

        def on_system_iteration_start(
            iteration: int, max_iter: int, agent_name: str, spec_path: str, period: int
        ) -> None:
            observed_system.append((iteration, spec_path))

        run_loop(
            max_iter=9,
            root=initialized_project,
            agent_pool=AgentPool([agent]),
            on_iteration_start=on_iteration_start,
            on_system_iteration_start=on_system_iteration_start,
        )

        regular_iters = [it for it, _ in observed_regular]
        system_iters = [it for it, _ in observed_system]

        # Regular runs every iteration 1..9
        assert regular_iters == list(range(1, 10))
        # System (every-3) runs at iters 3, 6, 9
        assert system_iters == [3, 6, 9]
        # System paths are all the cleanup spec
        assert all(sp == "specs/cleanup.every-3.spec.md" for _, sp in observed_system)

    def test_multiple_system_specs_same_iteration_alphabetical(
        self, initialized_project: Path
    ) -> None:
        """Multiple system specs fire in alphabetical order within one iteration."""
        (initialized_project / "specs").mkdir(exist_ok=True)
        (initialized_project / "specs" / "regular.spec.md").write_text("# Goal\nR")
        (initialized_project / "specs" / "z-cleanup.every-2.spec.md").write_text("# Goal\nZ")
        (initialized_project / "specs" / "a-cleanup.every-2.spec.md").write_text("# Goal\nA")

        agent = _RecordingAgent(initialized_project)
        agent.default_behavior = ("CONTINUE", False)

        system_calls: list[tuple[int, str]] = []

        def on_system_iteration_start(
            iteration: int, max_iter: int, agent_name: str, spec_path: str, period: int
        ) -> None:
            system_calls.append((iteration, spec_path))

        run_loop(
            max_iter=2,
            root=initialized_project,
            agent_pool=AgentPool([agent]),
            on_system_iteration_start=on_system_iteration_start,
        )

        # At iter 2, both system specs fire (alphabetical: a-cleanup first).
        iter2 = [(it, sp) for it, sp in system_calls if it == 2]
        assert iter2 == [
            (2, "specs/a-cleanup.every-2.spec.md"),
            (2, "specs/z-cleanup.every-2.spec.md"),
        ]

    def test_system_fires_in_same_iteration_as_regular(self, initialized_project: Path) -> None:
        """System and regular for iter N appear in the SAME iteration slot."""
        (initialized_project / "specs").mkdir(exist_ok=True)
        (initialized_project / "specs" / "regular.spec.md").write_text("# Goal\nR")
        (initialized_project / "specs" / "cleanup.every-2.spec.md").write_text("# Goal\nC")

        agent = _RecordingAgent(initialized_project)
        agent.default_behavior = ("CONTINUE", False)
        sequence: list[tuple[str, int, str]] = []

        def on_system_iteration_start(
            iteration: int, max_iter: int, agent_name: str, spec_path: str, period: int
        ) -> None:
            sequence.append(("SYSTEM", iteration, spec_path))

        def on_iteration_start(
            iteration: int, max_iter: int, done_count: int, agent_name: str, spec_path: str
        ) -> None:
            sequence.append(("REGULAR", iteration, spec_path))

        run_loop(
            max_iter=2,
            root=initialized_project,
            agent_pool=AgentPool([agent]),
            on_iteration_start=on_iteration_start,
            on_system_iteration_start=on_system_iteration_start,
        )

        # Iter 1: regular only (1%2!=0). Iter 2: system FIRST, then regular.
        iter1 = [item for item in sequence if item[1] == 1]
        iter2 = [item for item in sequence if item[1] == 2]
        assert iter1 == [("REGULAR", 1, "specs/regular.spec.md")]
        assert iter2 == [
            ("SYSTEM", 2, "specs/cleanup.every-2.spec.md"),
            ("REGULAR", 2, "specs/regular.spec.md"),
        ]


# =============================================================================
# Completion: only regular specs count
# =============================================================================


class TestCompletionCheck:
    """Exit check considers only regular specs."""

    def test_only_system_specs_exits_immediately(self, initialized_project: Path) -> None:
        """A project with only system specs exits 0 immediately."""
        (initialized_project / "specs").mkdir(exist_ok=True)
        (initialized_project / "specs" / "cleanup.every-3.spec.md").write_text("# Goal\nC")

        agent = _RecordingAgent(initialized_project)
        observed: list[tuple[int, str]] = []

        def on_iteration_start(
            iteration: int, max_iter: int, done_count: int, agent_name: str, spec_path: str
        ) -> None:
            observed.append((iteration, spec_path))

        def on_system_iteration_start(
            iteration: int, max_iter: int, agent_name: str, spec_path: str, period: int
        ) -> None:
            observed.append((iteration, spec_path))

        result = run_loop(
            max_iter=10,
            root=initialized_project,
            agent_pool=AgentPool([agent]),
            on_iteration_start=on_iteration_start,
            on_system_iteration_start=on_system_iteration_start,
        )

        assert result.exit_code == 0
        # No iterations ran — system specs cannot drive the loop alone.
        assert observed == []

    def test_all_regulars_done_exit_before_system(self, initialized_project: Path) -> None:
        """The exit check fires before the system phase — system gets no final run."""
        from ralph.core.specs import spec_content_hash

        (initialized_project / "specs").mkdir(exist_ok=True)
        (initialized_project / "specs" / "regular.spec.md").write_text("# Goal\nR")
        (initialized_project / "specs" / "cleanup.every-2.spec.md").write_text("# Goal\nC")

        # Pre-seed state with the regular at 3/3 so the loop exits at top.
        hash_r = spec_content_hash(initialized_project / "specs" / "regular.spec.md")
        write_multi_state(
            MultiSpecState(
                version=1,
                iteration=0,
                status=Status.DONE,
                current_index=0,
                specs=[
                    SpecProgress(
                        path="specs/regular.spec.md",
                        done_count=3,
                        last_status="DONE",
                        last_hash=hash_r,
                    )
                ],
            ),
            initialized_project,
        )

        agent = _RecordingAgent(initialized_project)
        observed_system: list[tuple[int, str]] = []

        def on_system_iteration_start(
            iteration: int, max_iter: int, agent_name: str, spec_path: str, period: int
        ) -> None:
            observed_system.append((iteration, spec_path))

        result = run_loop(
            max_iter=10,
            root=initialized_project,
            agent_pool=AgentPool([agent]),
            on_system_iteration_start=on_system_iteration_start,
        )

        assert result.exit_code == 0
        # System spec should NOT have run — exit check fires before system phase.
        assert observed_system == []


# =============================================================================
# File-change downgrade
# =============================================================================


class TestSystemSpecDowngrade:
    """When a system spec changes files, regulars at 3/3 are downgraded to 2/3."""

    def test_system_spec_changes_downgrade_regulars(self, initialized_project: Path) -> None:
        from ralph.core.specs import spec_content_hash

        (initialized_project / "specs").mkdir(exist_ok=True)
        (initialized_project / "specs" / "a.spec.md").write_text("# Goal\nA")
        (initialized_project / "specs" / "b.spec.md").write_text("# Goal\nB")
        (initialized_project / "specs" / "cleanup.every-2.spec.md").write_text("# Goal\nC")

        hash_a = spec_content_hash(initialized_project / "specs" / "a.spec.md")
        hash_b = spec_content_hash(initialized_project / "specs" / "b.spec.md")

        # b starts fresh, a at 3/3. We'll run until iter 2 when cleanup writes
        # a file and downgrades a.
        write_multi_state(
            MultiSpecState(
                version=1,
                iteration=0,
                status=Status.IDLE,
                current_index=1,  # b
                specs=[
                    SpecProgress(
                        path="specs/a.spec.md",
                        done_count=3,
                        last_status="DONE",
                        last_hash=hash_a,
                    ),
                    SpecProgress(path="specs/b.spec.md", done_count=0, last_hash=hash_b),
                ],
            ),
            initialized_project,
        )

        agent = _RecordingAgent(initialized_project)
        # Regular b always CONTINUE (so we don't exit too quickly).
        agent.behaviors = {
            "specs/a.spec.md": ("CONTINUE", False),
            "specs/b.spec.md": ("CONTINUE", False),
            "specs/cleanup.every-2.spec.md": ("CONTINUE", True),  # changes
        }

        run_loop(
            max_iter=2,
            root=initialized_project,
            agent_pool=AgentPool([agent]),
        )

        state = read_multi_state(initialized_project)
        assert state is not None
        # After iter 2 with system change, a should be downgraded from 3/3 to 2/3.
        a_entry = next(s for s in state.specs if s.path == "specs/a.spec.md")
        assert a_entry.done_count == 2

    def test_no_changes_no_downgrade(self, initialized_project: Path) -> None:
        from ralph.core.specs import spec_content_hash

        (initialized_project / "specs").mkdir(exist_ok=True)
        (initialized_project / "specs" / "a.spec.md").write_text("# Goal\nA")
        (initialized_project / "specs" / "cleanup.every-2.spec.md").write_text("# Goal\nC")

        hash_a = spec_content_hash(initialized_project / "specs" / "a.spec.md")
        write_multi_state(
            MultiSpecState(
                version=1,
                iteration=0,
                status=Status.IDLE,
                current_index=0,
                specs=[
                    SpecProgress(
                        path="specs/a.spec.md",
                        done_count=2,
                        last_status="DONE",
                        last_hash=hash_a,
                    )
                ],
            ),
            initialized_project,
        )

        agent = _RecordingAgent(initialized_project)
        # a CONTINUE (so it doesn't finish), cleanup CONTINUE no changes.
        agent.behaviors = {
            "specs/a.spec.md": ("CONTINUE", False),
            "specs/cleanup.every-2.spec.md": ("CONTINUE", False),
        }

        run_loop(
            max_iter=2,
            root=initialized_project,
            agent_pool=AgentPool([agent]),
        )

        state = read_multi_state(initialized_project)
        assert state is not None
        # a stays at 2 (no downgrade triggered by no-change system, no regular change)
        a_entry = next(s for s in state.specs if s.path == "specs/a.spec.md")
        assert a_entry.done_count == 2


# =============================================================================
# System specs do not write to state.json
# =============================================================================


class TestSystemSpecStateInvariant:
    """System specs MUST NOT cause state.json to gain an entry for them."""

    def test_system_spec_run_does_not_add_state_entry(self, initialized_project: Path) -> None:
        (initialized_project / "specs").mkdir(exist_ok=True)
        (initialized_project / "specs" / "regular.spec.md").write_text("# Goal\nR")
        (initialized_project / "specs" / "cleanup.every-2.spec.md").write_text("# Goal\nC")

        agent = _RecordingAgent(initialized_project)
        agent.default_behavior = ("CONTINUE", False)

        run_loop(
            max_iter=4,
            root=initialized_project,
            agent_pool=AgentPool([agent]),
        )

        state = read_multi_state(initialized_project)
        assert state is not None
        paths = {s.path for s in state.specs}
        assert "specs/cleanup.every-2.spec.md" not in paths
        assert "specs/regular.spec.md" in paths


# =============================================================================
# Iteration density: one regular spec per turn, system shares the slot
# =============================================================================


class TestIterationDensity:
    """The iteration counter advances exactly once per loop turn."""

    def test_one_regular_per_iteration(self, initialized_project: Path) -> None:
        (initialized_project / "specs").mkdir(exist_ok=True)
        (initialized_project / "specs" / "regular.spec.md").write_text("# Goal\nR")
        (initialized_project / "specs" / "cleanup.every-2.spec.md").write_text("# Goal\nC")

        agent = _RecordingAgent(initialized_project)
        agent.default_behavior = ("CONTINUE", False)
        regular_calls: list[int] = []

        def on_iteration_start(
            iteration: int, max_iter: int, done_count: int, agent_name: str, spec_path: str
        ) -> None:
            regular_calls.append(iteration)

        run_loop(
            max_iter=5,
            root=initialized_project,
            agent_pool=AgentPool([agent]),
            on_iteration_start=on_iteration_start,
        )

        # Each iteration runs the regular phase exactly once.
        assert regular_calls == [1, 2, 3, 4, 5]


# =============================================================================
# Concrete traces from the spec
# =============================================================================


class TestSpecTraces:
    """Concrete iteration traces from the spec (Trace A and Trace B)."""

    def test_trace_a_system_runs_alongside_regular(self, initialized_project: Path) -> None:
        """Trace A: regular runs every iteration; cleanup fires at iter 3."""
        (initialized_project / "specs").mkdir(exist_ok=True)
        (initialized_project / "specs" / "regular.spec.md").write_text("# Goal\nR")
        (initialized_project / "specs" / "cleanup.every-3.spec.md").write_text("# Goal\nC")

        agent = _RecordingAgent(initialized_project)
        agent.default_behavior = ("DONE", False)

        regular_log: list[tuple[int, str]] = []
        system_log: list[tuple[int, str]] = []

        def on_iteration_start(
            iteration: int, max_iter: int, done_count: int, agent_name: str, spec_path: str
        ) -> None:
            regular_log.append((iteration, spec_path))

        def on_system_iteration_start(
            iteration: int, max_iter: int, agent_name: str, spec_path: str, period: int
        ) -> None:
            system_log.append((iteration, spec_path))

        result = run_loop(
            max_iter=10,
            root=initialized_project,
            agent_pool=AgentPool([agent]),
            on_iteration_start=on_iteration_start,
            on_system_iteration_start=on_system_iteration_start,
        )

        assert result.exit_code == 0  # Goal achieved after 3 DONEs (3/3)
        # Iter 1: regular only. Iter 2: regular only. Iter 3: cleanup + regular.
        # Iter 4: exit check (regular at 3/3) → exit.
        assert regular_log == [
            (1, "specs/regular.spec.md"),
            (2, "specs/regular.spec.md"),
            (3, "specs/regular.spec.md"),
        ]
        # System runs at iter 3 only (1%3 and 2%3 != 0).
        assert system_log == [(3, "specs/cleanup.every-3.spec.md")]

    def test_trace_b_downgrade_and_recover(self, initialized_project: Path) -> None:
        """Trace B: system changes files at iter 2 → downgrade → re-verify."""
        from ralph.core.specs import spec_content_hash

        (initialized_project / "specs").mkdir(exist_ok=True)
        (initialized_project / "specs" / "a.spec.md").write_text("# Goal\nA")
        (initialized_project / "specs" / "b.spec.md").write_text("# Goal\nB")
        (initialized_project / "specs" / "cleanup.every-2.spec.md").write_text("# Goal\nC")

        hash_a = spec_content_hash(initialized_project / "specs" / "a.spec.md")
        hash_b = spec_content_hash(initialized_project / "specs" / "b.spec.md")

        # Setup: a at 3/3, b fresh.
        write_multi_state(
            MultiSpecState(
                version=1,
                iteration=0,
                status=Status.IDLE,
                current_index=0,
                specs=[
                    SpecProgress(
                        path="specs/a.spec.md",
                        done_count=3,
                        last_status="DONE",
                        last_hash=hash_a,
                    ),
                    SpecProgress(path="specs/b.spec.md", done_count=0, last_hash=hash_b),
                ],
            ),
            initialized_project,
        )

        agent = _RecordingAgent(initialized_project)
        # Agent behavior: a/b always DONE no changes; cleanup writes a file
        # on its FIRST invocation only.
        cleanup_call_count = {"n": 0}

        def invoke(
            prompt: str,
            timeout: int | None = 1800,
            output_file: Path | None = None,
            crash_patterns: list[str] | None = None,
        ) -> AgentResult:
            spec_path = ""
            for line in prompt.splitlines():
                s = line.strip()
                if s.startswith("Spec file:") or s.startswith("System spec file:"):
                    spec_path = s.split(":", 1)[1].strip()
                    break
            agent.invocations.append(spec_path)
            if "cleanup" in spec_path:
                cleanup_call_count["n"] += 1
                changes = cleanup_call_count["n"] == 1
                (initialized_project / ".ralph" / "status").write_text("CONTINUE")
                if changes:
                    (initialized_project / "test_output.txt").write_text("cleanup change 1")
                return AgentResult("ok", 0, None)
            (initialized_project / ".ralph" / "status").write_text("DONE")
            return AgentResult("ok", 0, None)

        agent.invoke = invoke  # type: ignore[method-assign]

        regular_log: list[tuple[int, str]] = []

        def on_iteration_start(
            iteration: int, max_iter: int, done_count: int, agent_name: str, spec_path: str
        ) -> None:
            regular_log.append((iteration, spec_path))

        result = run_loop(
            max_iter=12,
            root=initialized_project,
            agent_pool=AgentPool([agent]),
            on_iteration_start=on_iteration_start,
        )

        assert result.exit_code == 0
        # After iter 2's system change downgrades a from 3 to 2, the regular
        # phase must continue running regulars until both reach 3/3 again.
        # Both a and b must appear in the regular log AFTER iter 2 for
        # re-verification.
        post_iter2 = [(it, sp) for it, sp in regular_log if it >= 2]
        assert any("a.spec" in sp for _, sp in post_iter2)
        assert any("b.spec" in sp for _, sp in post_iter2)

        # Final state: both regulars at 3/3.
        final_state = read_multi_state(initialized_project)
        assert final_state is not None
        for spec in final_state.specs:
            assert spec.done_count >= 3, f"{spec.path} not done: {spec.done_count}"


# =============================================================================
# System spec status is ignored
# =============================================================================


class TestSystemSpecStatusIgnored:
    """A system spec's CONTINUE/DONE/STUCK signal is ignored by the loop."""

    def test_system_stuck_does_not_exit_loop(self, initialized_project: Path) -> None:
        """A STUCK from a system spec must NOT cause the loop to exit STUCK."""
        (initialized_project / "specs").mkdir(exist_ok=True)
        (initialized_project / "specs" / "regular.spec.md").write_text("# Goal\nR")
        (initialized_project / "specs" / "cleanup.every-2.spec.md").write_text("# Goal\nC")

        agent = _RecordingAgent(initialized_project)
        # regular DONE no changes; cleanup STUCK (should be ignored)
        agent.behaviors = {
            "specs/regular.spec.md": ("DONE", False),
            "specs/cleanup.every-2.spec.md": ("STUCK", False),
        }

        result = run_loop(
            max_iter=5,
            root=initialized_project,
            agent_pool=AgentPool([agent]),
        )

        # Loop should still exit 0 because the regular spec hits 3/3
        # despite the cleanup writing STUCK.
        assert result.exit_code == 0


# =============================================================================
# Backwards compatibility
# =============================================================================


class TestBackwardsCompatibility:
    """Old state.json files without every_n still load cleanly."""

    def test_old_state_with_every_n_field_loads(self, initialized_project: Path) -> None:
        """A legacy state.json that mistakenly stored every_n for a system spec
        is migrated cleanly — the system-spec entry is dropped."""
        (initialized_project / "specs").mkdir(exist_ok=True)
        (initialized_project / "specs" / "a.spec.md").write_text("# Goal\nA")
        (initialized_project / "specs" / "cleanup.every-3.spec.md").write_text("# Goal\nC")

        old_state = {
            "version": 1,
            "iteration": 5,
            "status": "CONTINUE",
            "current_index": 0,
            "specs": [
                {"path": "specs/a.spec.md", "done_count": 2},
                {
                    "path": "specs/cleanup.every-3.spec.md",
                    "done_count": 1,
                    "last_status": "DONE",
                    "every_n": 3,  # legacy field — must be tolerated/ignored
                },
            ],
        }
        (initialized_project / ".ralph" / "state.json").write_text(
            json.dumps(old_state), encoding="utf-8"
        )

        result = ensure_state(
            ["specs/a.spec.md", "specs/cleanup.every-3.spec.md"], initialized_project
        )
        paths = {s.path for s in result.specs}
        assert "specs/a.spec.md" in paths
        # System spec must not appear in state anymore.
        assert "specs/cleanup.every-3.spec.md" not in paths

    def test_existing_regular_spec_unaffected(self, initialized_project: Path) -> None:
        """Regular specs continue to work exactly as before."""
        (initialized_project / "specs").mkdir(exist_ok=True)
        (initialized_project / "specs" / "regular.spec.md").write_text("# Goal\nR")

        agent = _RecordingAgent(initialized_project)
        agent.default_behavior = ("DONE", False)

        result = run_loop(
            max_iter=10,
            root=initialized_project,
            agent_pool=AgentPool([agent]),
        )

        assert result.exit_code == 0

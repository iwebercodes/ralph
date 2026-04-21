"""Tests for ralph run command."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

from typer.testing import CliRunner

if TYPE_CHECKING:
    import pytest

from ralph.cli import app
from ralph.core.agent import AgentResult
from ralph.core.loop import IterationResult, LoopResult
from ralph.core.run_state import RunState, write_run_state
from ralph.core.state import (
    MultiSpecState,
    Status,
    ensure_state,
    get_history_dir,
    read_iteration,
    write_iteration,
    write_multi_state,
    write_status,
)
from tests.conftest import MockPi

runner = CliRunner()


class _UnavailableClaude:
    """Mock Claude agent that is unavailable."""
    name = "Claude"
    is_available = lambda self: False  # noqa: E731


class _UnavailableCodex:
    """Mock Codex agent that is unavailable."""
    name = "Codex"
    is_available = lambda self: False  # noqa: E731


class _AvailableClaude:
    """Mock Claude agent that is available."""
    name = "Claude"
    is_available = lambda self: True  # noqa: E731


class _AvailableCodex:
    """Mock Codex agent that is available."""
    name = "Codex"
    is_available = lambda self: True  # noqa: E731


class MockAgentForCLI:
    """Mock agent for CLI tests that writes status like a real agent would."""

    def __init__(self, root: Path):
        self._root = root
        self.responses: list[dict[str, object]] = []
        self.call_count = 0

    @property
    def name(self) -> str:
        return "MockAgent"

    def is_available(self) -> bool:
        return True

    def invoke(
        self,
        prompt: str,
        timeout: int = 1800,
        output_file: Path | None = None,
        crash_patterns: list[str] | None = None,
    ) -> AgentResult:
        idx = self.call_count
        self.call_count += 1

        if idx < len(self.responses):
            response = self.responses[idx]

            # Write status
            status_str = response.get("status", "CONTINUE")
            status = Status(status_str)
            write_status(status, self._root)

            # Make file changes
            for path_str in response.get("changes", []):
                path = self._root / path_str
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"modified by rotation {idx + 1}")

            output = str(response.get("output", "Mock output"))
            return AgentResult(output, 0, None)

        return AgentResult("Exhausted responses", 0, None)

    def is_exhausted(self, result: AgentResult) -> bool:
        return False


def test_run_not_initialized(temp_project: Path) -> None:
    """Test run fails when not initialized."""
    result = runner.invoke(app, ["run"])

    assert result.exit_code == 1
    assert "not initialized" in result.output


def test_run_no_prompt(initialized_project: Path) -> None:
    """Test run fails when PROMPT.md is missing."""
    result = runner.invoke(app, ["run"])

    assert result.exit_code == 1
    assert "No spec files" in result.output


def test_run_empty_prompt(initialized_project: Path) -> None:
    """Test run fails when PROMPT.md is empty."""
    (initialized_project / "PROMPT.md").write_text("")

    result = runner.invoke(app, ["run"])

    assert result.exit_code == 1
    assert "empty" in result.output.lower()


def test_run_no_claude(project_with_prompt: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test run fails when no AI agents are available."""
    # Remove all agents from PATH by setting empty PATH
    monkeypatch.setenv("PATH", "/nonexistent")

    result = runner.invoke(app, ["run"])

    assert result.exit_code == 1
    assert "no ai agents" in result.output.lower()


def test_run_fails_when_already_running(project_with_prompt: Path) -> None:
    """Test run exits when another run is active."""
    state = RunState(
        pid=os.getpid(),
        started_at="2025-01-19T14:30:00+00:00",
        iteration=1,
        max_iterations=20,
        agent="Codex",
        agent_started_at="2025-01-19T14:30:10+00:00",
    )
    write_run_state(state, project_with_prompt)

    result = runner.invoke(app, ["run"])

    assert result.exit_code == 1
    assert "already running" in result.output.lower()
    assert "inspect" in result.output.lower()


def test_run_single_iteration(
    project_with_prompt: Path,
) -> None:
    """Test run executes a single iteration."""
    mock_agent = MockAgentForCLI(project_with_prompt)
    mock_agent.responses = [
        {"status": "DONE", "output": "First iteration done", "changes": []},
        {"status": "DONE", "output": "Review 1", "changes": []},
        {"status": "DONE", "output": "Review 2", "changes": []},
    ]

    from ralph.core.pool import AgentPool

    mock_pool = AgentPool([mock_agent])

    with (
        patch("ralph.commands.run.ClaudeAgent") as mock_claude_cls,
        patch("ralph.commands.run.CodexAgent") as mock_codex_cls,
        patch("ralph.commands.run.AgentPool") as mock_pool_cls,
    ):
        # Make ClaudeAgent available, CodexAgent not available
        mock_claude_instance = mock_agent
        mock_codex_instance = _UnavailableCodex()
        mock_claude_cls.return_value = mock_claude_instance
        mock_codex_cls.return_value = mock_codex_instance
        mock_pool_cls.return_value = mock_pool

        result = runner.invoke(app, ["run", "--max", "10"])

    assert result.exit_code == 0
    assert "Goal achieved" in result.output
    assert read_iteration(project_with_prompt) == 3


def _run_with_mock_agent(project_path: Path, responses: list[dict], max_iter: int = 10):
    """Helper to run CLI with a mock agent."""
    from ralph.core.pool import AgentPool

    mock_agent = MockAgentForCLI(project_path)
    mock_agent.responses = responses
    mock_pool = AgentPool([mock_agent])

    with (
        patch("ralph.commands.run.ClaudeAgent") as mock_claude_cls,
        patch("ralph.commands.run.CodexAgent") as mock_codex_cls,
        patch("ralph.commands.run.AgentPool") as mock_pool_cls,
    ):
        mock_claude_cls.return_value = mock_agent
        mock_codex_cls.return_value = _UnavailableCodex()
        mock_pool_cls.return_value = mock_pool

        return runner.invoke(app, ["run", "--max", str(max_iter)])


def test_run_rotate_then_done(
    project_with_prompt: Path,
) -> None:
    """Test run handles ROTATE then DONE signals."""
    responses = [
        {"status": "ROTATE", "output": "Making progress", "changes": ["file1.py"]},
        {"status": "DONE", "output": "Finished", "changes": []},
        {"status": "DONE", "output": "Review 1", "changes": []},
        {"status": "DONE", "output": "Review 2", "changes": []},
    ]

    result = _run_with_mock_agent(project_with_prompt, responses)

    assert result.exit_code == 0
    assert read_iteration(project_with_prompt) == 4


def test_run_stuck_exits(
    project_with_prompt: Path,
) -> None:
    """Test run exits with code 2 on STUCK signal."""
    responses = [
        {"status": "STUCK", "output": "I'm blocked", "changes": []},
    ]

    result = _run_with_mock_agent(project_with_prompt, responses)

    assert result.exit_code == 2
    assert "stuck" in result.output.lower()


def test_run_max_iterations(
    project_with_prompt: Path,
) -> None:
    """Test run stops at max iterations."""
    # All ROTATE signals to keep going
    responses = [
        {"status": "ROTATE", "output": "Still working", "changes": [f"file{i}.py"]}
        for i in range(5)
    ]

    result = _run_with_mock_agent(project_with_prompt, responses, max_iter=3)

    assert result.exit_code == 3
    assert "max iterations" in result.output.lower()
    assert read_iteration(project_with_prompt) == 3


def test_run_done_with_changes_resets(
    project_with_prompt: Path,
) -> None:
    """Test DONE with changes resets verification count."""
    responses = [
        {"status": "DONE", "output": "Done but changed", "changes": ["file.py"]},
        {"status": "DONE", "output": "Really done", "changes": []},
        {"status": "DONE", "output": "Review 1", "changes": []},
    ]

    result = _run_with_mock_agent(project_with_prompt, responses)

    assert result.exit_code == 0
    # Took 3 iterations: 1 DONE with changes (1/3), then 2 consecutive DONEs (2/3, 3/3)
    assert read_iteration(project_with_prompt) == 3


def test_run_creates_history(
    project_with_prompt: Path,
) -> None:
    """Test run creates history log files."""
    responses = [
        {"status": "DONE", "output": "Done", "changes": []},
        {"status": "DONE", "output": "Review", "changes": []},
        {"status": "DONE", "output": "Review", "changes": []},
    ]

    _run_with_mock_agent(project_with_prompt, responses)

    history_dir = get_history_dir(project_with_prompt, "PROMPT.md")
    log_files = list(history_dir.glob("*.log"))
    assert len(log_files) == 3


def test_run_resume_from_previous(
    project_with_prompt: Path,
) -> None:
    """Test run resumes from previous iteration count."""
    write_iteration(5, project_with_prompt)

    responses = [
        {"status": "DONE", "output": "Done", "changes": []},
        {"status": "DONE", "output": "Review", "changes": []},
        {"status": "DONE", "output": "Review", "changes": []},
    ]

    result = _run_with_mock_agent(project_with_prompt, responses, max_iter=20)

    assert result.exit_code == 0
    assert read_iteration(project_with_prompt) == 8


# Tests for --agents option


def test_run_agents_unknown_name(
    project_with_prompt: Path,
) -> None:
    """Test --agents with unknown agent name shows error."""
    result = runner.invoke(app, ["run", "--agents", "foo"])

    assert result.exit_code == 1
    assert "unknown agent" in result.output.lower()
    assert "foo" in result.output.lower()


def test_run_agents_multiple_unknown_names(
    project_with_prompt: Path,
) -> None:
    """Test --agents with multiple unknown names shows sorted list."""
    result = runner.invoke(app, ["run", "--agents", "bar,foo"])

    assert result.exit_code == 1
    assert "unknown agent" in result.output.lower()
    # Both should be mentioned
    assert "bar" in result.output.lower()
    assert "foo" in result.output.lower()


def test_run_agents_partial_unknown(
    project_with_prompt: Path,
) -> None:
    """Test --agents with mixed known and unknown names."""
    result = runner.invoke(app, ["run", "--agents", "claude,foo"])

    assert result.exit_code == 1
    assert "unknown agent" in result.output.lower()
    assert "foo" in result.output.lower()


def test_run_agents_empty_string(
    project_with_prompt: Path,
) -> None:
    """Test --agents with empty string shows error."""
    result = runner.invoke(app, ["run", "--agents", ""])

    assert result.exit_code == 1
    assert "no agent names" in result.output.lower()


def test_run_agents_only_commas(
    project_with_prompt: Path,
) -> None:
    """Test --agents with only commas shows error."""
    result = runner.invoke(app, ["run", "--agents", ","])

    assert result.exit_code == 1
    assert "no agent names" in result.output.lower()


class NamedMockAgent(MockAgentForCLI):
    """Mock agent with configurable name."""

    def __init__(self, root: Path, name: str = "Claude"):
        super().__init__(root)
        self._agent_name = name

    @property
    def name(self) -> str:
        return self._agent_name


class RecordingMockAgent(MockAgentForCLI):
    """Mock agent that records every prompt it receives."""

    def __init__(self, root: Path):
        super().__init__(root)
        self.prompts: list[str] = []

    def invoke(
        self,
        prompt: str,
        timeout: int = 1800,
        output_file: Path | None = None,
        crash_patterns: list[str] | None = None,
    ) -> AgentResult:
        self.prompts.append(prompt)
        return super().invoke(prompt, timeout, output_file, crash_patterns)


def test_run_agents_claude_only(
    project_with_prompt: Path,
) -> None:
    """Test --agents claude filters to only Claude."""
    from ralph.core.pool import AgentPool

    mock_claude = NamedMockAgent(project_with_prompt, "Claude")
    mock_claude.responses = [
        {"status": "DONE", "output": "Done", "changes": []},
        {"status": "DONE", "output": "Review 1", "changes": []},
        {"status": "DONE", "output": "Review 2", "changes": []},
    ]

    mock_codex = type(
        "MockCodex",
        (),
        {"name": "Codex", "is_available": lambda self: True},
    )()

    captured_agents = []

    def capture_pool(agents):
        captured_agents.extend(agents)
        return AgentPool(agents)

    with (
        patch("ralph.commands.run.ClaudeAgent") as mock_claude_cls,
        patch("ralph.commands.run.CodexAgent") as mock_codex_cls,
        patch("ralph.commands.run.AgentPool", side_effect=capture_pool),
    ):
        mock_claude_cls.return_value = mock_claude
        mock_codex_cls.return_value = mock_codex

        result = runner.invoke(app, ["run", "--agents", "claude"])

    assert result.exit_code == 0
    # Only Claude should be in the pool
    assert len(captured_agents) == 1
    assert captured_agents[0].name == "Claude"


def test_run_agents_case_insensitive(
    project_with_prompt: Path,
) -> None:
    """Test --agents option is case-insensitive."""
    from ralph.core.pool import AgentPool

    mock_claude = NamedMockAgent(project_with_prompt, "Claude")
    mock_claude.responses = [
        {"status": "DONE", "output": "Done", "changes": []},
        {"status": "DONE", "output": "Review 1", "changes": []},
        {"status": "DONE", "output": "Review 2", "changes": []},
    ]

    mock_codex = type(
        "MockCodex",
        (),
        {"name": "Codex", "is_available": lambda self: True},
    )()

    captured_agents = []

    def capture_pool(agents):
        captured_agents.extend(agents)
        return AgentPool(agents)

    with (
        patch("ralph.commands.run.ClaudeAgent") as mock_claude_cls,
        patch("ralph.commands.run.CodexAgent") as mock_codex_cls,
        patch("ralph.commands.run.AgentPool", side_effect=capture_pool),
    ):
        mock_claude_cls.return_value = mock_claude
        mock_codex_cls.return_value = mock_codex

        result = runner.invoke(app, ["run", "--agents", "CLAUDE"])

    assert result.exit_code == 0
    assert len(captured_agents) == 1


def test_run_agents_whitespace_tolerance(
    project_with_prompt: Path,
) -> None:
    """Test --agents tolerates whitespace around names."""
    from ralph.core.pool import AgentPool

    mock_claude = NamedMockAgent(project_with_prompt, "Claude")
    mock_claude.responses = [
        {"status": "DONE", "output": "Done", "changes": []},
        {"status": "DONE", "output": "Review 1", "changes": []},
        {"status": "DONE", "output": "Review 2", "changes": []},
    ]

    # For this test, we need both agents to have the invoke method
    mock_codex = NamedMockAgent(project_with_prompt, "Codex")
    mock_codex.responses = mock_claude.responses

    captured_agents = []

    def capture_pool(agents):
        captured_agents.extend(agents)
        return AgentPool(agents)

    with (
        patch("ralph.commands.run.ClaudeAgent") as mock_claude_cls,
        patch("ralph.commands.run.CodexAgent") as mock_codex_cls,
        patch("ralph.commands.run.AgentPool", side_effect=capture_pool),
    ):
        mock_claude_cls.return_value = mock_claude
        mock_codex_cls.return_value = mock_codex

        result = runner.invoke(app, ["run", "--agents", " claude , codex "])

    assert result.exit_code == 0
    # Both agents should be included
    assert len(captured_agents) == 2


def test_run_agents_short_option(
    project_with_prompt: Path,
) -> None:
    """Test -a short option works."""
    result = runner.invoke(app, ["run", "-a", "foo"])

    assert result.exit_code == 1
    assert "unknown agent" in result.output.lower()


def test_run_agents_not_available(
    project_with_prompt: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test --agents shows specific error when agent not available."""
    # Remove all agents from PATH
    monkeypatch.setenv("PATH", "/nonexistent")

    result = runner.invoke(app, ["run", "--agents", "claude"])

    assert result.exit_code == 1
    # Should mention the specific agent and availability
    assert "claude" in result.output.lower()
    assert "not available" in result.output.lower()


def test_run_agents_shows_available_agents_in_error(
    project_with_prompt: Path,
) -> None:
    """Test unknown agent error shows available agent names."""
    result = runner.invoke(app, ["run", "--agents", "foo"])

    assert result.exit_code == 1
    # Error should list available agents
    assert "available agents" in result.output.lower()
    assert "claude" in result.output.lower()
    assert "codex" in result.output.lower()


def test_run_filter_option_filters_specs(temp_project: Path) -> None:
    """Test --filter option filters spec files by substring."""
    # Create a project with multiple specs
    runner.invoke(app, ["init"])

    # Create some spec files
    specs_dir = temp_project / "specs"
    specs_dir.mkdir()

    (specs_dir / "auth-login.spec.md").write_text("# Auth Login Spec\nImplement login")
    (specs_dir / "auth-register.spec.md").write_text("# Auth Register Spec\nImplement register")
    (specs_dir / "database-schema.spec.md").write_text("# Database Schema\nCreate DB schema")

    result = runner.invoke(app, ["run", "--filter", "auth", "--debug-prompt"])

    # Should use one of the auth specs
    assert result.exit_code == 0
    assert "Auth" in result.output
    assert "Database Schema" not in result.output


def test_run_filter_executes_only_matching_spec(temp_project: Path) -> None:
    """Filter controls execution path in the main loop (not debug mode)."""
    runner.invoke(app, ["init"])
    specs_dir = temp_project / "specs"
    specs_dir.mkdir()
    (specs_dir / "auth.spec.md").write_text("# Auth Spec\nImplement auth")
    (specs_dir / "user.spec.md").write_text("# User Spec\nImplement users")

    from ralph.core.pool import AgentPool

    mock_agent = RecordingMockAgent(temp_project)
    mock_agent.responses = [
        {"status": "DONE", "output": "done", "changes": []},
        {"status": "DONE", "output": "review-1", "changes": []},
        {"status": "DONE", "output": "review-2", "changes": []},
    ]
    mock_pool = AgentPool([mock_agent])

    with (
        patch("ralph.commands.run.ClaudeAgent") as mock_claude_cls,
        patch("ralph.commands.run.CodexAgent") as mock_codex_cls,
        patch("ralph.commands.run.AgentPool") as mock_pool_cls,
    ):
        mock_claude_cls.return_value = mock_agent
        mock_codex_cls.return_value = _UnavailableCodex()
        mock_pool_cls.return_value = mock_pool

        result = runner.invoke(app, ["run", "--filter", "auth", "--max", "5"])

    assert result.exit_code == 0
    assert mock_agent.prompts
    assert all("Spec file: specs/auth.spec.md" in prompt for prompt in mock_agent.prompts)
    assert all("Spec file: specs/user.spec.md" not in prompt for prompt in mock_agent.prompts)


def test_run_filter_resume_overrides_previous_current_spec(temp_project: Path) -> None:
    """Resuming with --filter re-prioritizes to filtered candidates."""
    runner.invoke(app, ["init"])
    specs_dir = temp_project / "specs"
    specs_dir.mkdir()
    (specs_dir / "auth.spec.md").write_text("# Auth Spec\nImplement auth")
    (specs_dir / "user.spec.md").write_text("# User Spec\nImplement users")

    discovered = sorted(["specs/auth.spec.md", "specs/user.spec.md"])
    state = ensure_state(discovered, temp_project)
    user_index = next(i for i, spec in enumerate(state.specs) if spec.path == "specs/user.spec.md")
    write_multi_state(
        MultiSpecState(
            version=state.version,
            iteration=state.iteration,
            status=state.status,
            current_index=user_index,
            specs=state.specs,
        ),
        temp_project,
    )

    from ralph.core.pool import AgentPool

    mock_agent = RecordingMockAgent(temp_project)
    mock_agent.responses = [{"status": "ROTATE", "output": "working", "changes": []}]
    mock_pool = AgentPool([mock_agent])

    with (
        patch("ralph.commands.run.ClaudeAgent") as mock_claude_cls,
        patch("ralph.commands.run.CodexAgent") as mock_codex_cls,
        patch("ralph.commands.run.AgentPool") as mock_pool_cls,
    ):
        mock_claude_cls.return_value = mock_agent
        mock_codex_cls.return_value = _UnavailableCodex()
        mock_pool_cls.return_value = mock_pool

        result = runner.invoke(app, ["run", "--filter", "auth", "--max", "1"])

    assert result.exit_code == 3
    assert mock_agent.prompts
    assert "Spec file: specs/auth.spec.md" in mock_agent.prompts[0]
    assert "Spec file: specs/user.spec.md" not in mock_agent.prompts[0]


def test_run_filter_option_case_insensitive(temp_project: Path) -> None:
    """Test --filter option is case-insensitive."""
    runner.invoke(app, ["init"])

    specs_dir = temp_project / "specs"
    specs_dir.mkdir()

    (specs_dir / "UserAuth.spec.md").write_text("# User Auth Spec\nImplement auth")

    result = runner.invoke(app, ["run", "--filter", "userauth", "--debug-prompt"])

    assert result.exit_code == 0
    assert "User Auth Spec" in result.output


def test_run_filter_no_match(temp_project: Path) -> None:
    """Test --filter with no matching specs shows error."""
    runner.invoke(app, ["init"])

    specs_dir = temp_project / "specs"
    specs_dir.mkdir()

    (specs_dir / "auth.spec.md").write_text("# Auth Spec")
    (specs_dir / "database.spec.md").write_text("# Database Spec")

    result = runner.invoke(app, ["run", "--filter", "payment"])

    assert result.exit_code == 1
    assert "No specs match filter" in result.output
    assert "payment" in result.output
    # Should list available specs
    assert "auth.spec.md" in result.output
    assert "database.spec.md" in result.output


def test_run_debug_prompt_outputs_prompt(project_with_prompt: Path) -> None:
    """Test --debug-prompt outputs the constructed prompt."""
    result = runner.invoke(app, ["run", "--debug-prompt"])

    assert result.exit_code == 0
    # Should contain the prompt template elements
    assert "RALPH LOOP - ROTATION" in result.output
    assert "YOUR GOAL" in result.output
    assert "CURRENT STATE" in result.output
    assert "GUARDRAILS" in result.output
    assert "COMPLETION SIGNALS" in result.output


def test_run_debug_prompt_with_filter(temp_project: Path) -> None:
    """Test --debug-prompt with --filter uses correct spec."""
    runner.invoke(app, ["init"])

    specs_dir = temp_project / "specs"
    specs_dir.mkdir()

    (specs_dir / "first.spec.md").write_text("# First Spec\nFirst goal")
    (specs_dir / "second.spec.md").write_text("# Second Spec\nSecond goal")

    result = runner.invoke(app, ["run", "--filter", "second", "--debug-prompt"])

    assert result.exit_code == 0
    assert "Second goal" in result.output
    assert "First goal" not in result.output


def test_run_multiple_rotations_show_independent_durations(project_with_prompt: Path) -> None:
    """Each rotation should display its own elapsed time."""

    class AvailableClaude:
        name = "Claude"

        def is_available(self) -> bool:
            return True

    class UnavailableCodex:
        name = "Codex"

        def is_available(self) -> bool:
            return False

    def fake_run_loop(*args, **kwargs):
        on_iteration_start = kwargs["on_iteration_start"]
        on_iteration_end = kwargs["on_iteration_end"]

        on_iteration_start(1, 10, 0, "Claude", "PROMPT.md")
        on_iteration_end(
            1,
            IterationResult(
                status=Status.ROTATE,
                files_changed=[],
                test_result=None,
                claude_output="rotation 1",
            ),
            0,
            "Claude",
            "PROMPT.md",
        )

        on_iteration_start(2, 10, 0, "Claude", "PROMPT.md")
        on_iteration_end(
            2,
            IterationResult(
                status=Status.DONE,
                files_changed=[],
                test_result=None,
                claude_output="rotation 2",
            ),
            1,
            "Claude",
            "PROMPT.md",
        )

        return LoopResult(exit_code=0, message="", iterations_run=2)

    with (
        patch("ralph.commands.run.ClaudeAgent", return_value=AvailableClaude()),
        patch("ralph.commands.run.CodexAgent", return_value=UnavailableCodex()),
        patch("ralph.commands.run.run_loop", side_effect=fake_run_loop),
        patch(
            "ralph.commands.run.time.time",
            side_effect=[0.0, 10.0, 55.0, 60.0, 193.0, 200.0],
        ),
    ):
        result = runner.invoke(app, ["run", "--max", "10"])

    assert result.exit_code == 0
    assert result.output.count("[ralph] Time:") == 2
    assert "[ralph] Time: 45s" in result.output
    assert "[ralph] Time: 2m 13s" in result.output


# ---- Integration tests with mock Pi CLI ----


def test_run_with_mock_pi_single_iteration(
    project_with_prompt: Path,
    mock_pi: MockPi,
) -> None:
    """Test run executes a full iteration using the real PiAgent calling mock pi CLI."""
    mock_pi.set_responses([
        {"status": "DONE", "output": "Task completed", "changes": []},
        {"status": "DONE", "output": "Review 1", "changes": []},
        {"status": "DONE", "output": "Review 2", "changes": []},
    ])

    # Make Claude and Codex unavailable so only Pi is selected
    with (
        patch("ralph.commands.run.ClaudeAgent") as mock_claude_cls,
        patch("ralph.commands.run.CodexAgent") as mock_codex_cls,
    ):
        mock_claude_cls.return_value = _UnavailableClaude()
        mock_codex_cls.return_value = _UnavailableCodex()

        result = runner.invoke(app, ["run", "--agents", "pi", "--max", "10"])

    assert result.exit_code == 0
    assert "Goal achieved" in result.output
    # PiAgent was invoked 3 times (1 implementation + 2 reviews)
    assert read_iteration(project_with_prompt) == 3


def test_run_with_mock_pi_creates_files(
    project_with_prompt: Path,
    mock_pi: MockPi,
) -> None:
    """Test that mock pi can create files that Ralph detects."""
    mock_pi.set_responses([
        {
            "status": "DONE",
            "output": "Created calculator module",
            "changes": ["calculator.py", "test_calculator.py"],
        },
        {"status": "DONE", "output": "Verified", "changes": []},
        {"status": "DONE", "output": "Verified", "changes": []},
    ])

    with (
        patch("ralph.commands.run.ClaudeAgent") as mock_claude_cls,
        patch("ralph.commands.run.CodexAgent") as mock_codex_cls,
    ):
        mock_claude_cls.return_value = _UnavailableClaude()
        mock_codex_cls.return_value = _UnavailableCodex()

        result = runner.invoke(app, ["run", "--agents", "pi", "--max", "10"])

    assert result.exit_code == 0
    # Verify files were created by the mock
    assert (project_with_prompt / "calculator.py").exists()
    assert (project_with_prompt / "test_calculator.py").exists()
    assert read_iteration(project_with_prompt) == 3


def test_run_with_mock_pi_rotate_then_done(
    project_with_prompt: Path,
    mock_pi: MockPi,
) -> None:
    """Test full flow: ROTATE signal then DONE, all via real PiAgent + mock pi."""
    mock_pi.set_responses([
        {"status": "ROTATE", "output": "Still working on this", "changes": ["work_in_progress.py"]},
        {"status": "DONE", "output": "Finished the task", "changes": []},
        {"status": "DONE", "output": "Review 1", "changes": []},
        {"status": "DONE", "output": "Review 2", "changes": []},
    ])

    with (
        patch("ralph.commands.run.ClaudeAgent") as mock_claude_cls,
        patch("ralph.commands.run.CodexAgent") as mock_codex_cls,
    ):
        mock_claude_cls.return_value = _UnavailableClaude()
        mock_codex_cls.return_value = _UnavailableCodex()

        result = runner.invoke(app, ["run", "--agents", "pi", "--max", "10"])

    assert result.exit_code == 0
    assert read_iteration(project_with_prompt) == 4


def test_run_with_mock_pi_done_with_changes_resets(
    project_with_prompt: Path,
    mock_pi: MockPi,
) -> None:
    """Test that DONE with changes resets the verification count (real PiAgent path)."""
    mock_pi.set_responses([
        {"status": "DONE", "output": "Done but changed", "changes": ["revised.py"]},
        {"status": "DONE", "output": "Verified clean", "changes": []},
        {"status": "DONE", "output": "Review 1", "changes": []},
    ])

    with (
        patch("ralph.commands.run.ClaudeAgent") as mock_claude_cls,
        patch("ralph.commands.run.CodexAgent") as mock_codex_cls,
    ):
        mock_claude_cls.return_value = _UnavailableClaude()
        mock_codex_cls.return_value = _UnavailableCodex()

        result = runner.invoke(app, ["run", "--agents", "pi", "--max", "10"])

    assert result.exit_code == 0
    # 1 DONE with changes (1/3) + 2 more clean reviews (2/3, 3/3) = 3 total iterations
    assert read_iteration(project_with_prompt) == 3


def test_run_with_mock_pi_stuck_exits(
    project_with_prompt: Path,
    mock_pi: MockPi,
) -> None:
    """Test that STUCK signal from pi causes exit code 2."""
    mock_pi.set_responses([
        {"status": "STUCK", "output": "I'm blocked and can't proceed", "changes": []},
    ])

    with (
        patch("ralph.commands.run.ClaudeAgent") as mock_claude_cls,
        patch("ralph.commands.run.CodexAgent") as mock_codex_cls,
    ):
        mock_claude_cls.return_value = _UnavailableClaude()
        mock_codex_cls.return_value = _UnavailableCodex()

        result = runner.invoke(app, ["run", "--agents", "pi", "--max", "10"])

    assert result.exit_code == 2
    assert "stuck" in result.output.lower()


def test_run_with_mock_pi_exhaustion_detection(
    project_with_prompt: Path,
    mock_pi: MockPi,
) -> None:
    """Test that PiAgent correctly detects exhaustion from mock pi error output."""
    # First call returns an error with rate limit pattern
    mock_pi.set_responses([
        {
            "status": "CONTINUE",
            "output": "",
            "changes": [],
            "exit_code": 1,
            "error": "Error: rate_limit exceeded - try again in 30 seconds",
        },
    ])

    with (
        patch("ralph.commands.run.ClaudeAgent") as mock_claude_cls,
        patch("ralph.commands.run.CodexAgent") as mock_codex_cls,
    ):
        mock_claude_cls.return_value = _UnavailableClaude()
        mock_codex_cls.return_value = _UnavailableCodex()

        result = runner.invoke(app, ["run", "--agents", "pi", "--max", "10"])

    # The agent should detect exhaustion and the pool should be empty
    assert result.exit_code == 4
    assert "all agents exhausted" in result.output.lower()


def test_run_with_mock_pi_exits_at_max_iterations(
    project_with_prompt: Path,
    mock_pi: MockPi,
) -> None:
    """Test that run stops at max iterations even with mock pi."""
    mock_pi.set_responses([
        {"status": "ROTATE", "output": "Still working", "changes": [f"file{i}.py"]}
        for i in range(5)
    ])

    with (
        patch("ralph.commands.run.ClaudeAgent") as mock_claude_cls,
        patch("ralph.commands.run.CodexAgent") as mock_codex_cls,
    ):
        mock_claude_cls.return_value = _UnavailableClaude()
        mock_codex_cls.return_value = _UnavailableCodex()

        result = runner.invoke(app, ["run", "--agents", "pi", "--max", "3"])

    assert result.exit_code == 3
    assert "max iterations" in result.output.lower()
    assert read_iteration(project_with_prompt) == 3


def test_run_agents_pi_only(
    project_with_prompt: Path,
    mock_pi: MockPi,
) -> None:
    """Test --agents pi filters to only Pi agent."""
    mock_pi.set_responses([
        {"status": "DONE", "output": "Done", "changes": []},
        {"status": "DONE", "output": "Review 1", "changes": []},
        {"status": "DONE", "output": "Review 2", "changes": []},
    ])

    with (
        patch("ralph.commands.run.ClaudeAgent") as mock_claude_cls,
        patch("ralph.commands.run.CodexAgent") as mock_codex_cls,
    ):
        mock_claude_cls.return_value = _UnavailableClaude()
        mock_codex_cls.return_value = _UnavailableCodex()

        result = runner.invoke(app, ["run", "--agents", "pi"])

    assert result.exit_code == 0
    assert "Goal achieved" in result.output
    assert read_iteration(project_with_prompt) == 3


def test_run_agents_pi_with_other_available(
    project_with_prompt: Path,
    mock_pi: MockPi,
) -> None:
    """Test --agents pi filters to only Pi even when Claude/Codex are available."""
    from ralph.core.pool import AgentPool

    captured_agents: list[str] = []

    def capture_pool(agents):
        captured_agents.extend(a.name for a in agents)
        return AgentPool(agents)

    with (
        patch("ralph.commands.run.ClaudeAgent") as mock_claude_cls,
        patch("ralph.commands.run.CodexAgent") as mock_codex_cls,
        patch("ralph.commands.run.PiAgent") as mock_pi_cls,
        patch("ralph.commands.run.AgentPool", side_effect=capture_pool),
    ):
        # Claude and Codex are "available" (not patched to be unavailable)
        mock_claude_cls.return_value = _AvailableClaude()
        mock_codex_cls.return_value = _AvailableCodex()
        mock_pi_cls.return_value = mock_pi

        # noqa: F841
        runner.invoke(app, ["run", "--agents", "pi"])

    # Only Pi should be in the pool (Claude and Codex filtered out by --agents pi)
    assert captured_agents == ["Pi"]

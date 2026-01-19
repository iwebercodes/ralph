"""Tests for ralph run command."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

from typer.testing import CliRunner

if TYPE_CHECKING:
    import pytest

from ralph.cli import app
from ralph.core.agent import AgentResult
from ralph.core.state import Status, read_iteration, write_iteration, write_status

runner = CliRunner()


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

    def invoke(self, prompt: str, timeout: int = 1800) -> AgentResult:
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
    assert "PROMPT.md" in result.output


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
        mock_codex_instance = type("MockCodex", (), {"is_available": lambda self: False})()
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
        mock_codex_cls.return_value = type("MockCodex", (), {"is_available": lambda self: False})()
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
        {"status": "DONE", "output": "Review 2", "changes": []},
    ]

    result = _run_with_mock_agent(project_with_prompt, responses)

    assert result.exit_code == 0
    # Took 4 iterations: 1 DONE with changes, then 3 consecutive DONEs
    assert read_iteration(project_with_prompt) == 4


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

    history_dir = project_with_prompt / ".ralph" / "history"
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

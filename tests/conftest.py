"""Pytest fixtures for Ralph tests."""

from __future__ import annotations

import os
import stat
import sys
from collections.abc import Generator
from pathlib import Path

import pytest

from ralph.core.state import (
    GUARDRAILS_TEMPLATE,
    HANDOFF_TEMPLATE,
    HISTORY_DIR,
    RALPH_DIR,
    Status,
    write_done_count,
    write_guardrails,
    write_handoff,
    write_iteration,
    write_status,
)

IS_WINDOWS = sys.platform == "win32"


@pytest.fixture
def temp_project(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary project directory."""
    original_cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        yield tmp_path
    finally:
        os.chdir(original_cwd)


@pytest.fixture
def initialized_project(temp_project: Path) -> Path:
    """Create a temporary project with Ralph initialized."""
    ralph_dir = temp_project / RALPH_DIR
    ralph_dir.mkdir()
    (ralph_dir / HISTORY_DIR).mkdir()

    write_status(Status.IDLE, temp_project)
    write_iteration(0, temp_project)
    write_done_count(0, temp_project)
    write_handoff(HANDOFF_TEMPLATE, temp_project)
    write_guardrails(GUARDRAILS_TEMPLATE, temp_project)

    return temp_project


@pytest.fixture
def project_with_prompt(initialized_project: Path) -> Path:
    """Create an initialized project with a PROMPT.md."""
    prompt = initialized_project / "PROMPT.md"
    prompt.write_text("# Goal\n\nTest goal content.\n\n# Success Criteria\n\n- [ ] Test passes")
    return initialized_project


class MockClaude:
    """Mock Claude CLI for testing."""

    def __init__(self, project_path: Path):
        # Store mock files outside the project directory to avoid being tracked
        import tempfile

        self._mock_dir = Path(tempfile.mkdtemp())
        self._project_path = project_path
        self.responses: list[dict[str, object]] = []
        self.call_count = 0
        self._script_path: Path | None = None
        self._responses_file = self._mock_dir / "mock_responses.txt"
        self._count_file = self._mock_dir / "call_count"

    def setup(self) -> Path:
        """Set up the mock claude script and return the bin directory."""
        bin_dir = self._mock_dir / "mock_bin"
        bin_dir.mkdir(exist_ok=True)

        # Use the actual python executable path
        python_path = sys.executable

        # Create a Python script that will be called
        py_script = bin_dir / "mock_claude.py"
        py_script_content = f'''import sys
import json
import os
from pathlib import Path

responses_file = Path(r"{self._responses_file}")
count_file = Path(r"{self._count_file}")
ralph_dir = Path(os.getcwd()) / ".ralph"

if responses_file.exists():
    with open(responses_file) as f:
        responses = json.load(f)

    # Read call count
    if count_file.exists():
        idx = int(count_file.read_text())
    else:
        idx = 0

    if idx < len(responses):
        response = responses[idx]

        # Write status
        status = response.get("status", "CONTINUE")
        (ralph_dir / "status").write_text(status)

        # Make file changes
        for path in response.get("changes", []):
            Path(path).write_text(f"modified by rotation {{idx + 1}}")

        # Write output
        print(response.get("output", "Mock Claude output"))

    # Increment call count
    count_file.write_text(str(idx + 1))

sys.exit(0)
'''
        py_script.write_text(py_script_content)

        if IS_WINDOWS:
            # On Windows, create a .cmd wrapper
            script = bin_dir / "claude.cmd"
            script.write_text(f'@"{python_path}" "{py_script}" %*\n')
        else:
            # On Unix, create a shell script with shebang
            script = bin_dir / "claude"
            script.write_text(f'#!/bin/sh\n"{python_path}" "{py_script}" "$@"\n')
            script.chmod(script.stat().st_mode | stat.S_IEXEC)

        self._script_path = script
        return bin_dir

    def set_responses(self, responses: list[dict[str, object]]) -> None:
        """Set the responses the mock will return."""
        self.responses = responses
        import json

        self._responses_file.write_text(json.dumps(responses))

        # Reset call count
        self._count_file.write_text("0")


@pytest.fixture
def mock_claude(temp_project: Path, monkeypatch: pytest.MonkeyPatch) -> MockClaude:
    """Create a mock Claude CLI.

    Note: Uses temp_project fixture to ensure mock is in same directory.
    """
    mock = MockClaude(temp_project)
    bin_dir = mock.setup()

    # Prepend mock bin to PATH (use os.pathsep for cross-platform compatibility)
    original_path = os.environ.get("PATH", "")
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{original_path}")

    return mock

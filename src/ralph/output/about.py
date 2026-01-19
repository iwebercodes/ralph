"""About text for ralph --about command."""

from __future__ import annotations

ABOUT_TEXT = """\
RALPH - Autonomous Development Supervisor

Ralph is a CLI tool that supervises autonomous coding tasks. You invoke Ralph
to manage a task with fresh-context rotations and verification — Ralph handles
the details so you can work on the goal.

WORKFLOW
--------

1. Initialize:  ralph init
2. Write the task goal and success criteria to PROMPT.md
3. Start:       ralph run
4. Check:       ralph status

Ralph runs available AI agents in fresh-context rotations until the goal is complete.
When completion is signaled, Ralph verifies 3 times with fresh context before
declaring success.

WHAT TO PUT IN PROMPT.md
------------------------

Write a clear goal and specific success criteria:

  # Goal
  Implement user authentication with JWT tokens.

  # Success Criteria
  - [ ] Users can register with email/password
  - [ ] Users can log in and receive JWT token
  - [ ] Protected routes require valid token
  - [ ] Tests pass: pytest tests/

COMMANDS
--------

  ralph init [--force]
      Initialize Ralph in the current directory.
      --force: Overwrite existing .ralph/ directory

  ralph run [--max N] [--test-cmd "..."] [--agents NAMES] [--no-color]
      Execute rotations until the goal is complete.
      --max N: Maximum iterations (default: 20)
      --test-cmd: Command to run after each iteration
      --agents: Comma-separated agent names to use (e.g., "claude,codex")

  ralph status [--json]
      Show current state without running.
      --json: Output as JSON

  ralph reset [--keep-guardrails] [--keep-history]
      Clear state and start fresh.
      --keep-guardrails: Preserve guardrails.md
      --keep-history: Preserve history/ directory

  ralph history [N] [--list] [--tail N]
      View logs from previous rotations.
      N: Rotation number to view
      --list: List all rotations with summary
      --tail N: Show last N lines of log

  ralph --about
      Show this help (what you're reading now)

EXIT CODES
----------

  0   Success — goal completed and verified
  2   Stuck — needs human intervention
  3   Max iterations reached — increase --max or simplify goal
  4   All agents exhausted — wait for rate limits to reset

HOW RALPH WORKS
---------------

Ralph breaks tasks into fresh-context rotations to prevent context loss and
premature completion:

  1. Each rotation starts with clean context (no accumulated confusion)
  2. Progress persists via state files (nothing is lost between rotations)
  3. When "DONE" is signaled, Ralph verifies 3x with fresh context
  4. Only after 3 consecutive verifications is the goal truly complete

The supervised agent handles internal protocol (handoff.md, guardrails.md,
status signals). You just write PROMPT.md and run Ralph.
"""


def get_about_text() -> str:
    """Return the about text."""
    return ABOUT_TEXT

# Changelog

## v0.1.0 - Initial Release

First public release of Ralph, an autonomous supervisor for Claude Code.

### What Ralph Does

Ralph watches Claude Code work on your tasks and ensures they actually get finished. Instead of declaring "done" prematurely or losing context on complex tasks, Ralph keeps Claude on track until your success criteria are verified.

### Features

**Context Rotation**
- Automatically breaks long tasks into fresh-context chunks
- Saves progress between rotations so nothing is lost
- Prevents context pollution that causes Claude to forget earlier decisions

**Triple Verification**
- When Claude signals "done", Ralph verifies 3 times with fresh sessions
- Catches premature completion before you waste time checking yourself
- Only marks complete when no changes are made across all verification rounds

**Commands**
- `ralph init` — Initialize Ralph in your project directory
- `ralph run` — Start the supervision loop until completion
- `ralph status` — Check current progress without running
- `ralph reset` — Clear state and start fresh on a new task
- `ralph history` — View logs from previous work sessions

**Run Options**
- `--max N` — Set maximum iterations (default: 20)
- `--test-cmd "..."` — Run tests after each iteration
- `--no-color` — Disable colored output for CI environments

**Scripting Support**
- Exit code 0: Success
- Exit code 2: Claude is stuck and needs human help
- Exit code 3: Hit max iterations

### Installation

```bash
pipx install ralph-loop
```

### Requirements

- Python 3.10+
- Claude CLI installed and configured

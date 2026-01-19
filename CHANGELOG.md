# Changelog

## v0.2.0 - Multi-Agent Support

Ralph can now work with multiple AI agents and rotate between them when one hits rate limits.

### Added

- **Multiple agents**: Ralph now supports both Claude and Codex. When one agent hits rate limits, Ralph automatically switches to the other and keeps working.

- **`--agents` option**: Filter which agents to use with `ralph run --agents claude` or `ralph run --agents codex`. Useful for testing or when you only have one CLI installed.

- **Exit code 4**: New exit code when all agents are exhausted (rate limited). Wait for limits to reset, then run again.

### Changed

- **Agent abstraction**: Internally refactored from hardcoded Claude to a flexible Agent protocol. This makes it easier to add more agents in the future.

- **History logs**: Now show which agent ran each rotation, making it easier to debug multi-agent sessions.

### Fixed

- **False exhaustion detection**: Previously, if your PROMPT.md mentioned "rate limit" (e.g., in test descriptions), Ralph might incorrectly think the agent was rate limited. Now only actual error messages trigger exhaustion.

## v0.1.4 - Reliability Fix & AI Agent Support

Fixes a bug that caused Ralph to get stuck in loops, and adds a way to teach AI agents how to use Ralph.

### Fixed

- **Stuck in endless loops**: Ralph could get stuck repeating "ROTATE" or "CONTINUE" forever without making progress. This happened when the status file wasn't cleared between iterations. Now each iteration starts fresh, so Ralph reliably moves forward.

- **False "Goal achieved!" exits**: In rare cases, Ralph would declare success when work wasn't actually done. The fix ensures Ralph only sees completion signals that Claude actually sends, not leftover data from previous runs.

### Added

- **`ralph --about` flag**: Teaching an AI agent to use Ralph is now as simple as telling it to run `ralph --about`. The output explains everything the agent needs: how to invoke Ralph, what to put in PROMPT.md, command options, and exit codes. Perfect for using Ralph from Claude Code, Cursor, or other AI coding tools.

## v0.1.3 - Better Verification & Unicode Fix

Improves the verification cycle and fixes a Windows bug that caused encoding errors.

### Fixed

- **Windows Unicode bug**: Files with emojis or non-ASCII characters (Chinese, Japanese, umlauts) now work correctly. Root cause: `Path.read_text()` defaulted to cp1252 on Windows instead of UTF-8.

### Improved

- **Separate IMPLEMENT and REVIEW prompts**: Previously both modes used identical instructions. Now REVIEW mode explicitly tells Claude to be skeptical, verify independently, and not trust the previous rotation's handoff blindly.
- **Better guardrails guidance**: Added instructions on what makes good guardrails (specific, actionable, project-specific) and when to update them.
- **Verification progress**: REVIEW mode now shows "verification pass 2 of 3" so Claude knows where it is in the cycle.

### Added

- **Cross-platform integration tests**:
  - Full file-to-prompt pipeline tests
  - Windows line endings (CRLF), UTF-8 BOM, mixed encodings
  - Large files, special characters ({}, %, \)
- **CI improvements**: `publish.yml` now tests on all 3 platforms before releasing to PyPI
- **Mascot**: Added Ralph the supervisor dog to README

## v0.1.2 - Windows Compatibility

Fixes for Windows platform support.

### Fixed

- File snapshots now use forward slashes consistently across all platforms
- Mock Claude CLI works correctly on Windows (uses .cmd wrapper)
- subprocess calls find executables with .cmd extension on Windows

## v0.1.1 - Documentation Updates

- Changed recommended install method to `pipx install ralph-loop`
- Fixed Python version requirement in docs (3.10+, not 3.8+)
- Added GitHub Actions workflow for automated PyPI publishing

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

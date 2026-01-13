# Changelog

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

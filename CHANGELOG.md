# Changelog

## v0.6.0 - Scheduled Specs, No-Sleep Mode & Resumable Runs

This release adds scheduled (periodic) spec execution via `.every-[n].spec.md` filenames, preventing OS sleep during long-running Ralph sessions, and the `--continue` flag for resuming interrupted runs. It also introduces a spec-writing skill for consistent spec creation, switches CI to uv for dependency resolution consistency, and improves verification accuracy by removing handoff injection from REVIEW prompts.

### Added

- **Scheduled (periodic) spec execution**: Spec files matching `.every-[n].spec.md` (e.g., `cleanup.every-5.spec.md`) run only on every n-th rotation (`iteration % n == 0`), skipping on other rotations while staying in the pool. Useful for cleanup, consolidation, and maintenance tasks that don't need to run every rotation. Scheduled specs get priority when their turn arrives, and gap-filling runs other eligible specs during skip iterations.

- **No-sleep mode**: Ralph now prevents OS sleep/hibernation automatically during runs on Linux (via `systemd-inhibit`), macOS (`caffeinate`), and Windows (`SetThreadExecutionState`). This is essential for multi-hour unattended agent loops — system sleep would kill running processes. No CLI flag needed; always active by default since it's core to Ralph's purpose. Cleanly released on any exit path (success, error, Ctrl+C, crash).

- **`--continue` / `-c` flag**: Resume interrupted runs from where they left off. Reads saved configuration (`--agents`, `--max`, `--timeout`, `--filter`) from `.ralph/run_config.json`. Explicit CLI flags override saved values. Solves the problem of losing run configuration after Ctrl+C or crashes.

- **Spec-writing skill**: `.agents/skills/spec-writing/SKILL.md` provides shared guidance on writing effective spec files for Ralph. Covers spec anatomy (Problem → Goal → Success Criteria → Constraints → Notes), verifiable success criteria, file naming conventions, common patterns, and a review checklist.

### Changed

- **REVIEW prompt no longer includes handoff**: Removed "CLAIMED STATE" section from REVIEW prompts to prevent false verification — models were trusting prior rotation claims without independently checking. Review agents now inspect code and tests from a fresh POV.

- **CI/CD uses `uv` for dependency resolution**: Both CI workflows (`.github/workflows/ci.yml` and `publish.yml`) now use `uv sync --extra dev` instead of pip, ensuring CI resolves dependencies identically to local development. Fixes mypy strict type check failures caused by version mismatches between pip and uv.

- **Spec state tracking enhanced**: Each spec now tracks its scheduled period (`every_n`) in state.json, persisted only when > 1 for backward compatibility with older versions.

### Fixed

- **Bare `PathSpec` type annotation**: Updated type annotations in `core/ignore.py`, `core/no_sleep.py`, and `core/snapshot.py` to use `pathspec.PathSpec` instead of bare `PathSpec`, fixing mypy strict checks with pathspec 1.1+.

### QA

- **Comprehensive scheduled specs test suite**: 973 lines of tests covering period parsing, eligibility checking, gap-filling, priority ordering, completion detection, and edge cases (every-0, every-abc, multiple periods, legacy state compatibility).
- **No-sleep mode test suite**: 863 lines of tests covering each platform, cleanup paths, edge cases, and live smoke tests verifying real inhibitor registration.

## v0.5.0 - Agent Pool Expansion, CLI Enhancements & Performance Tuning

This release adds the Pi agent as a third backend option (alongside Claude and Codex), enhances the CLI with global flags and JSON output, improves token efficiency with less aggressive counter resets, and adds rotation timing display.

### Added

- **Pi agent support**: Ralph now supports the Pi coding agent as a third backend alongside Claude and Codex, enabling local LLM integration: `--agent pi` (or `-a pi`). The PiAgent class implements the full Agent protocol with robust exhaustion detection for rate limits, quota exceeded, and model unavailable errors. Pi is included in the default agent pool by default.

- **Global CLI flags**: `--version` and `--about` flags are now available on all commands (not just `ralph run`), providing consistent access to version info and project overview regardless of which subcommand you use.

- **`--filter` option**: Filter specs by pattern with `ralph run --filter <pattern>` to focus on specific specifications.

- **`--debug-prompt` option**: Inspect the generated prompt before sending it to agents with `ralph run --debug-prompt`.

- **Enhanced `ralph reset`**: Selective reset flags for targeted state clearing: `--reset-handoff`, `--reset-counters`, `--reset-verification`, and `--reset-all`.

- **JSON output support**: Both `ralph inspect` and `ralph status` now support `--json` flag for machine-readable output, useful for scripting and automation.

- **Rotation timing display**: Each rotation now shows human-readable duration (`Time: Xm Ys`) to help identify performance bottlenecks and understand which specs consume the most time.

- **Content hash tracking**: Spec prioritization now uses content hashes to track file modifications more accurately, improving the reliability of smart sorting.

- **Per-spec status tracking**: Each spec now tracks its last status and file modifications independently, enabling better state management across rotations.

### Changed

- **Less aggressive counter resets**: Verification counters are now reset more conservatively:
  - DONE specs with no changes: increment counter (up to 3/3)
  - DONE specs with changes: reset to 1/3 (not 0/3)
  - Non-DONE specs with changes: reset to 0/3
  - Non-DONE specs without changes: keep counter unchanged
  - File changes only downgrade other fully verified specs from 3/3 to 2/3
  This significantly reduces token usage by avoiding unnecessary re-processing.

- **Default agent pool**: The default pool now includes all three agents (Claude, Codex, Pi) instead of just Claude and Codex.

### Fixed

- **Agent exhaustion detection**: Improved detection for both Claude and Codex agents, removing exhausted agents from the pool gracefully with clean exit when all agents are exhausted.

- **Mock agent protocol compliance**: All mock agent classes in tests now implement `exhaustion_reason()` to satisfy the Agent protocol strictly.

### QA

- **Pre-commit hooks**: Added `.pre-commit-config.yaml` with ruff-format, ruff linting, and mypy strict type checking, matching CI pipeline checks.
- **Comprehensive QA spec**: Added `specs/qa.spec.md` requiring all code to pass static analysis compliance.

## v0.4.0 - Multi-Spec Workflow

Work on multiple specifications simultaneously without regressions, with intelligent prioritization.

### Added

- **Multi-spec mode**: Ralph can now handle multiple specification files at once, ensuring all constraints remain satisfied:
  - Discovers specs from `PROMPT.md`, `.ralph/specs/*.spec.md`, and `specs/*.spec.md`
  - Round-robin rotation through all specs with independent verification tracking
  - Resets all counters when any file changes, preventing regressions
  - Each spec maintains its own handoff and history for better context isolation
  - Shared guardrails enable knowledge transfer between specs

- **Smart spec prioritization**: Specs are now intelligently sorted to process the most relevant ones first:
  - New specs (never processed) get highest priority
  - Modified specs come next
  - Active specs (non-DONE status) before completed ones
  - DONE specs that modified files before those that didn't
  - Significantly improves performance with many specs

- **Agent crash recovery**: Ralph now gracefully handles agent crashes and hangs:
  - Detects crashes via exit codes, empty output, or error patterns
  - Real-time stderr monitoring catches hung processes
  - Automatically continues with next rotation instead of stopping
  - Crash details preserved in handoff for context

- **`ralph --version` command**: Check installed version with `ralph --version` or `-V`

- **Agent removal notifications**: Visual feedback when agents are removed from the pool due to exhaustion, showing which agent and why

- **Comprehensive `.ralphignore`**: Expanded ignore patterns for Python development files prevent false rotation resets

### Fixed

- **Codex exhaustion detection**: Fixed false positives where Codex was incorrectly removed from pool when stderr contained informational mentions of "token limit". Now requires both non-zero exit code and specific error patterns.

## v0.3.0 - Session Monitoring

Monitor running Ralph sessions from another terminal with `ralph inspect`.

### Added

- **`ralph inspect` command**: When Ralph runs for extended periods, there's no visibility into progress—you can't tell if it's making headway, stuck, or about to finish. Now you can monitor from another terminal:
  - See current status: iteration number, active agent, start time, last update
  - `--follow` flag: tail agent output in real-time (like `tail -f`)
  - `--json` flag: machine-readable output for scripts and integrations

- **Run state tracking**: Ralph now writes `.ralph/run.json` with PID, iteration, agent, and timestamps. The current agent's output streams to `.ralph/current.log`.

- **Concurrent run prevention**: `ralph run` now fails fast if already running in the same directory, preventing accidental parallel sessions that could corrupt state.

- **Configurable timeouts**: Agents like Codex can run for hours on complex tasks. The previous 30-minute default was too aggressive.
  - `--timeout` flag: customize per-rotation timeout (default: 3 hours)
  - `--no-timeout` flag: disable timeout entirely for very long tasks

### Fixed

- **Codex failing silently in non-git directories**: Codex would exit with empty output without required directory trust flags, causing Ralph to loop indefinitely. Now works correctly in any project directory.

- **Agent errors hidden from history**: stderr output from agents wasn't captured in history logs, making failures hard to diagnose. Agent errors now appear in log files.

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

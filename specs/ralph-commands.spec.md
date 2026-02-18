# Ralph Commands Specification

## Goal

This spec defines all Ralph CLI commands, their arguments, options, and expected behavior. Any changes to command interfaces must be reflected here.

## Commands Overview

Ralph provides six main commands for managing and executing AI-driven development workflows, plus two global options:

### 1. `ralph init`

**Purpose**: Initialize Ralph in the current directory

**Syntax**: `ralph init [OPTIONS]`

**Options**:
- `--force` / `-f` (bool, default: false): Overwrite existing .ralph/ directory

**Behavior**:
- Creates `.ralph/` directory structure if it doesn't exist:
  - `.ralph/history/` - Directory for iteration logs
  - `.ralph/handoffs/` - Directory for spec-specific handoff files
- Initializes state files:
  - `.ralph/state.json` - Multi-spec state with structure:
    ```json
    {
      "version": 1,
      "iteration": 0,
      "status": "IDLE",
      "current_index": 0,
      "specs": []
    }
    ```
  - `.ralph/status` - Contains current status (IDLE)
  - `.ralph/iteration` - Contains iteration number (0)
  - `.ralph/done_count` - Contains done count (0)
  - `.ralph/handoff.md` - Legacy handoff file with template sections
  - `.ralph/guardrails.md` - Guardrails file with header "# Guardrails"
- Creates `PROMPT.md` template in project root if it doesn't exist
- Fails if `.ralph/` exists unless `--force` is used
- Shows success message with next steps

**Error Cases**:
- Directory already initialized (without --force)
- Permission issues creating directories
- Invalid current directory

### 2. `ralph history`

**Purpose**: View logs from previous rotations

**Syntax**: `ralph history [ROTATION] [OPTIONS]`

**Arguments**:
- `rotation` (int, optional): Specific rotation number to view. If omitted, shows most recent.

**Options**:
- `--list` / `-l` (bool, default: false): List all rotations with summary
- `--tail` / `-n` (int, optional): Show last N lines of log

**Behavior**:
- With no args: Shows most recent rotation log
- With `--list`: Shows numbered list of all rotations with timestamps and status
- With rotation number: Shows specific rotation's full log
- With `--tail N`: Shows last N lines of specified rotation (or most recent)
- Displays in pager for long outputs
- Shows "No history available" if no rotations exist

**Error Cases**:
- Ralph not initialized
- Invalid rotation number
- No history available

### 3. `ralph inspect`

**Purpose**: Show whether Ralph is currently running and its live status

**Syntax**: `ralph inspect [OPTIONS]`

**Options**:
- `--follow` / `-f` (bool, default: false): After showing status, tail the live agent output log
- `--json` (bool, default: false): Output machine-readable JSON for scripting

**Behavior**:
- Checks if Ralph is currently running via PID file
- Shows current iteration, status, and runtime information
- With `--follow`: Continuously displays live agent output
- With `--json`: Outputs structured data for programmatic use
- Shows "Not running" if no active process

**JSON Output Format**:
```json
{
  "running": true,
  "pid": 12345,
  "iteration": 3,
  "max_iterations": 20,
  "status": "CONTINUE",
  "runtime": "2m 45s",
  "current_agent": "claude"
}
```

**Error Cases**:
- Ralph not initialized
- Stale PID file (process no longer exists)

### 4. `ralph reset`

**Purpose**: Reset Ralph iteration counter to start a new rotation cycle

**Syntax**: `ralph reset [OPTIONS]`

**Options**:
- `--reset-guardrails` (bool, default: false): Reset guardrails.md to template
- `--reset-history` (bool, default: false): Clear history/ directory
- `--reset-counter` (bool, default: false): Reset verification counter (done_count) to 0
- `--reset-handoffs` (bool, default: false): Reset all handoff files to template

**Behavior**:
- Always resets iteration count to 0
- Always resets status to IDLE
- By default, preserves:
  - Guardrails content
  - History logs
  - Verification counters (done_count)
  - Handoff files
  - Spec priority information (last_status, last_hash, modified_files)
- With `--reset-guardrails`: Resets guardrails.md to "# Guardrails"
- With `--reset-history`: Removes all history logs
- With `--reset-counter`: Resets done_count to 0 for all specs
- With `--reset-handoffs`: Resets all handoff files to template
- Shows confirmation of what was reset and what was preserved

**Error Cases**:
- Ralph not initialized
- Ralph currently running
- Permission issues deleting files

### 5. `ralph status`

**Purpose**: Show current Ralph state without running anything

**Syntax**: `ralph status [OPTIONS]`

**Options**:
- `--json` (bool, default: false): Output as JSON

**Behavior**:
- Shows current iteration number and max iterations
- Displays current status (IDLE, CONTINUE, ROTATE, DONE, STUCK)
- Shows done count (number of completed specs)
- Displays goal preview from PROMPT.md
- Shows spec progress if in multi-spec mode

**JSON Output Format**:
```json
{
  "iteration": 5,
  "max_iterations": 20,
  "status": "CONTINUE",
  "done_count": 2,
  "goal": "Implement user authentication system",
  "specs": [
    {"path": "specs/auth.spec.md", "status": "DONE"},
    {"path": "specs/login.spec.md", "status": "CONTINUE"}
  ]
}
```

**Error Cases**:
- Ralph not initialized

### 6. `ralph run`

**Purpose**: Execute the Ralph loop until completion or max iterations

**Syntax**: `ralph run [OPTIONS]`

**Options**:
- `--max` / `-m` (int, default: 20): Maximum number of iterations
- `--agents` / `-a` (str, optional): Comma-separated agent names (e.g., 'claude' or 'codex')
- `--timeout` (int, default: 10800): Timeout per rotation in seconds (default: 3 hours)
- `--no-timeout` (bool, default: false): Disable timeout entirely (run until completion)
- `--no-color` (bool, default: false): Disable colored output
- `--filter` (str, optional): Filter specs by substring match in filename
- `--debug-prompt` (bool, default: false): Output the fully constructed prompt to stdout instead of executing agents, then exit

**Behavior**:
- Validates Ralph is initialized and not already running
- For each rotation:
  1. Discovers all available specs from filesystem
  2. If `--filter` provided, removes specs whose filename doesn't contain the substring
  3. Sorts the remaining specs according to priority rules (failed specs first, etc.)
  4. Executes the highest priority spec from the filtered and sorted list
- Creates agent pool from available agents (defaults to claude,codex)
- Shows timing for each rotation
- Handles Ctrl+C gracefully with state preservation
- Stops on DONE status or max iterations reached
- Displays final summary with total time and results

**Filter Behavior**:
- Case-insensitive substring matching against spec filenames
- Matches against basename only (not full path)
- Filter is applied **after** spec discovery but **before** priority sorting on each rotation
- When resuming an interrupted run with `--filter`, the filter overrides current position and re-prioritizes
- State for all specs is preserved but only filtered specs are candidates for execution
- Example use case: After Ralph starts working on spec_2, you interrupt and restart with `--filter spec_1` - Ralph will return to spec_1 regardless of previous position
- Examples:
  - `--filter auth` matches `user-auth.spec.md`, `oauth-setup.spec.md`
  - `--filter login` matches `login-flow.spec.md`, `login-validation.spec.md`
- If no specs match filter, shows error and exits
- Filter applies to both new and resumed runs
- Filter applies to both single and multi-spec mode

**Debug Prompt Behavior**:
- Outputs the complete constructed prompt that would be sent to the agent
- Includes all components:
  - Goal (from spec file content)
  - Current handoff state
  - Guardrails
  - Iteration information
  - File paths for spec and handoff
- Outputs to stdout for inspection or piping to other tools
- Exits immediately after outputting prompt (no agent execution)
- Useful for debugging prompt construction and testing with external tools
- Example usage: `ralph run --filter "auth.spec.md" --debug-prompt | claude`

**Agent Selection**:
- Checks agent availability (API keys, rate limits)
- Falls back to available agents if requested agent unavailable
- Shows warning if no agents available
- Supports 'claude' and 'codex' agents

**Error Cases**:
- Ralph not initialized
- Already running (PID conflict)
- No agents available
- No specs match filter criteria
- Timeout exceeded (if not disabled)

**Implementation Note**:
The filter logic must be applied within the rotation loop itself, not just during initial validation. On each rotation, the execution loop must:
1. Discover all specs
2. Apply the filter to remove non-matching specs
3. Sort the filtered specs by priority
4. Execute the highest priority filtered spec

This ensures that using `--filter` when resuming allows switching to any filtered spec regardless of the previous execution position.

**Critical Testing Requirement**:
The filter MUST be tested with actual execution, not just `--debug-prompt` mode. A test that only verifies debug output is insufficient - the filter must actually control which specs are executed during the main loop.

## Global Options

### `ralph --help` / `ralph COMMAND --help`

**Purpose**: Display help information for Ralph or specific commands

**Syntax**: 
- `ralph --help` - Show general Ralph help
- `ralph COMMAND --help` - Show help for specific command

**Behavior**:
- Shows command descriptions, options, and usage examples
- Available for all commands
- Exits after displaying help

### `ralph --version`

**Purpose**: Display the current Ralph version

**Syntax**: `ralph --version`

**Behavior**:
- Outputs version string in format "ralph X.Y.Z"
- Version matches `__version__` in `src/ralph/__init__.py`
- Can be used with any command context
- Exits after displaying version (doesn't execute other commands)

**Example Output**:
```
ralph 0.4.0
```

**Error Cases**:
- Version string malformed in source code
- Import issues with __init__.py

### `ralph --about`

**Purpose**: Display comprehensive explanation of how Ralph works

**Syntax**: `ralph --about`

**Behavior**:
- Shows detailed information about Ralph's purpose and workflow
- Includes command overview with all options
- Explains workflow steps (init → write PROMPT.md → run → inspect/status)
- Documents exit codes and their meanings
- Describes Ralph's rotation-based approach and verification process
- Provides examples of good PROMPT.md content
- Exits after displaying information (doesn't execute other commands)

**Content Sections**:
- Ralph overview and purpose
- Workflow steps (5-step process)
- PROMPT.md guidance with examples
- Complete command reference
- Exit codes documentation
- How Ralph works (rotation and verification explanation)

**Error Cases**:
- Import issues with about text module

## Common Patterns

### Error Handling
All commands check for Ralph initialization and provide helpful error messages with suggested actions.

### JSON Output
Commands that support `--json` output structured data suitable for scripting and integration.

### Color Support
The `ralph run` command supports `--no-color` for CI/scripting environments. Other commands use minimal coloring that respects terminal capabilities automatically.

### Path Resolution
All commands work with the current working directory and automatically discover relevant files.

### State Management
Commands interact consistently with Ralph's state system for progress tracking and configuration.

## Success Criteria

1. **Interface Consistency**: All commands follow consistent option naming patterns
2. **Error Messages**: Clear, actionable error messages for all failure cases
3. **Help Text**: Comprehensive help for all options and arguments
4. **JSON Support**: Machine-readable output where applicable
5. **Graceful Handling**: Proper signal handling and state preservation
6. **Filter Implementation**: `--filter` option works correctly for spec filtering:
   - **MUST TEST**: Create project with specs `auth.spec.md` and `user.spec.md`
   - **MUST TEST**: Run `ralph run --filter auth` and verify ONLY `auth.spec.md` is processed
   - **MUST TEST**: Interrupt while processing `user.spec.md`, then run `ralph run --filter auth` and verify it switches to `auth.spec.md`
   - **MUST TEST**: Filter works with actual execution, not just `--debug-prompt` mode
7. **Version Display**: `ralph --version` correctly displays current version
8. **About Display**: `ralph --about` shows comprehensive help information
9. **Reset Command Behavior**: All reset options work as specified:
   - **MUST TEST**: `ralph reset` preserves guardrails, history, counters, handoffs by default
   - **MUST TEST**: Each `--reset-*` flag works independently
   - **MUST TEST**: Combined flags work together
10. **Spec-Implementation Alignment**: Implementation must exactly match this specification:
   - No command behavior exists that is not described in this spec
   - When commands or options are removed from spec, they must be removed from implementation
   - When commands or options are added to spec, they must be added to implementation
   - All default values, types, and behaviors must match specification exactly

## Testing Requirements

The implementation must include comprehensive unit and integration tests that automatically verify all functionality described in this specification, including but not limited to:

1. **Command Behavior**: All commands work as specified with correct defaults and options
2. **Error Handling**: All error cases produce appropriate error messages and exit codes
3. **State Management**: State files are created, read, and updated correctly
4. **Option Processing**: All command-line options work as documented
5. **Edge Cases**: Boundary conditions and edge cases are handled gracefully
6. **Integration**: Commands interact correctly with each other and the file system

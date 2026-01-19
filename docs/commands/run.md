# ralph run

Execute the Ralph loop until the goal is complete or max iterations is reached.

## Usage

```bash
ralph run [--max N] [--test-cmd CMD] [--agents NAMES] [--no-color]
```

## What It Does

1. Discovers available AI agents (Claude, Codex, etc.)
2. Builds a prompt from PROMPT.md and current state
3. Runs an agent with that prompt
4. Saves progress to handoff.md
5. Repeats until the agent signals DONE (verified 3 times) or max iterations

If an agent becomes rate limited, Ralph automatically rotates to another available agent.

## Options

| Option | Description | Default |
|--------|-------------|---------|
| `--max`, `-m` | Maximum iterations before stopping | 20 |
| `--test-cmd`, `-t` | Command to run after each iteration | None |
| `--agents`, `-a` | Comma-separated agent names to use | All available |
| `--no-color` | Disable colored output | False |

## Examples

**Basic run:**
```bash
ralph run
```

**Increase max iterations for complex tasks:**
```bash
ralph run --max 50
```

**Run tests after each iteration:**
```bash
ralph run --test-cmd "pytest"
ralph run --test-cmd "npm test"
```

The test command runs after each rotation. Test results are logged but don't stop the loop.

**Disable colors (for CI/logs):**
```bash
ralph run --no-color
```

**Use only a specific agent:**
```bash
ralph run --agents claude        # Only use Claude
ralph run --agents codex         # Only use Codex
ralph run -a claude,codex        # Use both (explicit)
```

This is useful for testing with a specific agent or when you want to avoid using one temporarily.

## Output Explained

```
╭─────────────────────────────────────────────────────────╮
│  RALPH LOOP                                             │
│  Autonomous development with context rotation           │
╰─────────────────────────────────────────────────────────╯

  ╭── Claude working... ──────────────────────────────────╮
  │  Iteration:    1/20                                   │
  ├── Rotation complete ──────────────────────────────────┤
  │  Result:       CONTINUE                               │
  │  Files:        3 files changed                        │
  ╰───────────────────────────────────────────────────────╯

  ╭── Claude reviewing... ────────────────────────────────╮
  │  Iteration:    2/20 [REVIEW]                          │
  ├── Rotation complete ──────────────────────────────────┤
  │  Result:       DONE                                   │
  │  Files:        no changes                             │
  │  Verification: 1/3 [●○○]                              │
  ╰───────────────────────────────────────────────────────╯

  ╭── Codex working... ───────────────────────────────────╮
  │  Iteration:    3/20                                   │
  ...

  ╭───────────────────────────────────────────────────────╮
  │  ✓ COMPLETE                                           │
  │  Goal achieved after 4 iterations (3/3 verified)      │
  │  Time: 2m 15s                                         │
  ╰───────────────────────────────────────────────────────╯
```

- **Agent name** - Shows which agent is working (Claude, Codex, etc.)
- **Iteration** - Rotation number / max iterations
- **[REVIEW]** - Indicates a verification rotation
- **Result** - What the agent signaled ([see signals](../concepts/status-signals.md))
- **Files** - How many files were modified
- **Verification** - Progress toward 3x verification (shown on DONE)

## Exit Codes

| Code | Meaning | What to do |
|------|---------|------------|
| 0 | Success | Goal completed! |
| 2 | STUCK | Agent needs help. [See troubleshooting](../troubleshooting/ralph-stuck.md) |
| 3 | Max iterations | Task may be too large. [See troubleshooting](../troubleshooting/max-iterations.md) |
| 4 | All agents exhausted | All agents rate limited. Wait and retry. [See troubleshooting](../troubleshooting/agent-errors.md) |
| 1 | Error | Check error message |

## Interrupting

Press `Ctrl+C` to stop Ralph. State is saved automatically.

```
^C
Interrupted. State saved.

  State: iteration 3 (interrupted)

To resume: ralph run
To reset: ralph reset
```

To continue where you left off:
```bash
ralph run
```

## Related

- [ralph status](./status.md) - Check state without running
- [ralph reset](./reset.md) - Start fresh
- [Agents](../concepts/agents.md) - How Ralph works with multiple agents
- [Troubleshooting](../troubleshooting/index.md) - When things go wrong

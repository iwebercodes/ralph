# ralph run

Execute the Ralph loop until the goal is complete or max iterations is reached.

## Usage

```bash
ralph run [--max N] [--test-cmd CMD] [--no-color]
```

## What It Does

1. Builds a prompt from PROMPT.md and current state
2. Runs Claude with that prompt
3. Saves progress to handoff.md
4. Repeats until Claude signals DONE (verified 3 times) or max iterations

## Options

| Option | Description | Default |
|--------|-------------|---------|
| `--max`, `-m` | Maximum iterations before stopping | 20 |
| `--test-cmd`, `-t` | Command to run after each iteration | None |
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

## Output Explained

```
RALPH  Supervising Claude...

[1/20] Working...
  Signal: CONTINUE
  Files changed: 3

[2/20] Working...
  Signal: DONE
  Files changed: 0 (1/3 verification)

[3/20] Working...
  Signal: DONE
  Files changed: 0 (2/3 verification)

[4/20] Working...
  Signal: DONE
  Files changed: 0 (3/3 verification)

Goal achieved in 4 rotations (2m 15s)
```

- **[1/20]** - Rotation number / max iterations
- **Signal** - What Claude signaled ([see signals](../concepts/status-signals.md))
- **Files changed** - How many files were modified
- **Verification** - Progress toward 3x verification

## Exit Codes

| Code | Meaning | What to do |
|------|---------|------------|
| 0 | Success | Goal completed! |
| 2 | STUCK | Claude needs help. [See troubleshooting](../troubleshooting/ralph-stuck.md) |
| 3 | Max iterations | Task may be too large. [See troubleshooting](../troubleshooting/max-iterations.md) |
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
- [Troubleshooting](../troubleshooting/index.md) - When things go wrong

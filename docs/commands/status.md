# ralph status

Show current Ralph state without running anything.

## Usage

```bash
ralph status [--json]
```

## What It Does

Displays the current state of Ralph in this directory:
- Current iteration number
- Status signal
- Verification progress
- Goal preview

Useful for checking progress after an interruption or between runs.

## Options

| Option | Description |
|--------|-------------|
| `--json` | Output as JSON (for scripting) |

## Examples

**Check current status:**
```bash
ralph status
```

Output:
```
Ralph Status
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Iteration:  5 / 20
  Status:     CONTINUE
  Done count: 0 / 3
  Goal:       Add JWT-based user authentication...
```

**JSON output (for scripts):**
```bash
ralph status --json
```

```json
{
  "initialized": true,
  "iteration": 5,
  "max_iterations": 20,
  "status": "CONTINUE",
  "done_count": 0,
  "goal_preview": "Add JWT-based user authentication..."
}
```

## Output Explained

| Field | Meaning |
|-------|---------|
| Iteration | Current rotation / max allowed |
| Status | Last signal from Claude ([see signals](../concepts/status-signals.md)) |
| Done count | Verification progress (0-3) |
| Goal | First line of your PROMPT.md |

## Use Cases

**After Ctrl+C:** Check where you left off before resuming.

**In scripts:** Use `--json` to programmatically check state.

**Debugging:** See if Ralph is stuck in a loop or making progress.

## Related

- [ralph run](./run.md) - Continue or start execution
- [Status signals](../concepts/status-signals.md) - What each status means

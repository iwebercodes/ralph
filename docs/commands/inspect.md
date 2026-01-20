# ralph inspect

Check whether a Ralph run is currently active and view live status.

## Usage

```bash
ralph inspect [--follow] [--json]
```

## What It Does

- Reads `.ralph/run.json` to see if a run is active
- Shows PID, start time, current iteration, and agent name
- Optionally tails the live output log

## Options

| Option | Description |
|--------|-------------|
| `--follow`, `-f` | After showing status, tail the live agent output log |
| `--json` | Output machine-readable JSON |

## Examples

**Check running status:**
```bash
ralph inspect
```

**JSON output (for scripts):**
```bash
ralph inspect --json
```

**Follow live agent output:**
```bash
ralph inspect --follow
```

**Tail the log directly:**
```bash
tail -f .ralph/current.log
```

## Output Explained

| Field | Meaning |
|-------|---------|
| Started | How long ago the run began |
| Iteration | Current rotation / max allowed |
| Agent | Active agent name |
| Running for | How long the current agent has been running |

## Related

- [ralph run](./run.md) - Start a loop
- [ralph status](./status.md) - Show stored state

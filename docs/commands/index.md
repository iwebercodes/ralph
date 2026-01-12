# Commands

Ralph has five commands. Here's when to use each one.

## Command Summary

| Command | Description |
|---------|-------------|
| [`ralph init`](./init.md) | Initialize Ralph in the current directory |
| [`ralph run`](./run.md) | Execute the loop until the goal is complete |
| [`ralph status`](./status.md) | Show current state without running |
| [`ralph reset`](./reset.md) | Clear state and start fresh |
| [`ralph history`](./history.md) | View logs from previous rotations |

## Typical Workflow

```bash
# 1. Start a new project
ralph init

# 2. Edit PROMPT.md with your goal

# 3. Run until complete
ralph run

# 4. Check progress (if interrupted)
ralph status

# 5. Start over (for a new task)
ralph reset
```

## Quick Reference

```bash
# Initialize
ralph init
ralph init --force          # Overwrite existing .ralph/

# Run
ralph run
ralph run --max 30          # Increase max iterations
ralph run --test-cmd "npm test"  # Run tests after each iteration
ralph run --no-color        # Disable colored output

# Check status
ralph status
ralph status --json         # Output as JSON

# Reset
ralph reset
ralph reset --keep-guardrails  # Preserve learned lessons
ralph reset --keep-history     # Preserve logs

# View history
ralph history               # Most recent rotation
ralph history 5             # Specific rotation
ralph history --list        # Summary of all rotations
ralph history --tail 50     # Last 50 lines
```

## Exit Codes

The `ralph run` command returns different exit codes:

| Code | Meaning |
|------|---------|
| 0 | Success - goal completed |
| 2 | Claude signaled STUCK - needs human help |
| 3 | Hit max iterations - task may be too large |
| 1 | Other error |

Use these in scripts:
```bash
ralph run && echo "Success!" || echo "Something went wrong"
```

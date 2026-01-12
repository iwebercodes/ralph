# ralph reset

Reset Ralph state to start fresh.

## Usage

```bash
ralph reset [--keep-guardrails] [--keep-history]
```

## What It Does

Clears Ralph's state so you can start a new task:
- Resets iteration counter to 0
- Clears handoff.md
- Sets status to IDLE
- Optionally preserves guardrails and history

Does NOT modify PROMPT.md - you'll need to edit that yourself for a new task.

## Options

| Option | Description |
|--------|-------------|
| `--keep-guardrails` | Preserve lessons learned |
| `--keep-history` | Keep rotation logs |

## Examples

**Full reset:**
```bash
ralph reset
```

Output:
```
Reset complete.
  Iteration: 0
  Status: IDLE
  Guardrails: cleared
  History: cleared
```

**Keep guardrails (lessons from previous runs):**
```bash
ralph reset --keep-guardrails
```

Use this when starting a new task in the same project. Guardrails contain useful lessons Claude learned (e.g., "always run tests before marking done").

**Keep history (for debugging):**
```bash
ralph reset --keep-history
```

Use this when you want to reference old logs while working on a new task.

**Keep both:**
```bash
ralph reset --keep-guardrails --keep-history
```

## When to Use Reset

**Starting a new task:** Reset before editing PROMPT.md for something different.

**Something went wrong:** Reset clears potentially corrupted state.

**Task got stuck:** Reset and try with a better prompt.

## Reset vs Init --force

| Command | What it does |
|---------|--------------|
| `ralph reset` | Clears state, keeps `.ralph/` structure |
| `ralph init --force` | Deletes `.ralph/` completely, recreates |

Use `reset` for normal workflow. Use `init --force` only if the directory structure itself is corrupted.

## Related

- [ralph run](./run.md) - Start working on the new task
- [Guardrails](../concepts/guardrails.md) - What gets cleared or kept

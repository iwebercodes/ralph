# ralph init

Initialize Ralph in the current directory.

## Usage

```bash
ralph init [--force]
```

## What It Does

Creates the Ralph directory structure and a PROMPT.md template:

```
.ralph/
├── handoff.md      # State between rotations
├── guardrails.md   # Learned lessons
├── status          # Current status signal
├── iteration       # Current iteration number
├── done_count      # Verification counter
└── history/        # Logs from each rotation

PROMPT.md           # Your goal (created if missing)
```

## Options

| Option | Description |
|--------|-------------|
| `--force`, `-f` | Overwrite existing `.ralph/` directory |

## Examples

**Basic initialization:**
```bash
cd my-project
ralph init
```

Output:
```
Initialized Ralph in .ralph/
Created PROMPT.md template

Next steps:
  1. Edit PROMPT.md with your goal
  2. Run: ralph run
```

**Reinitialize (start fresh):**
```bash
ralph init --force
```

This clears all state and starts over. Use this when you want a clean slate.

## Common Issues

**".ralph/ already exists"**

You've already initialized Ralph in this directory. Either:
- Use `ralph reset` to clear state but keep the setup
- Use `ralph init --force` to completely reinitialize

## Next Steps

After initializing:
1. [Edit PROMPT.md](../writing-prompts.md) with your goal
2. [Run Ralph](./run.md) to start working

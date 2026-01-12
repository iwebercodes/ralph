# Getting Started

Get from zero to your first successful Ralph run in under 5 minutes.

## Prerequisites

Before you start, you need:

- **Python 3.10 or higher** - Check with `python --version`
- **Claude CLI** - The command-line tool from Anthropic

If you don't have Claude CLI installed, get it from [claude.ai/download](https://claude.ai/download). After installing, verify it works:

```bash
claude --version
```

## Install Ralph

```bash
pipx install ralph-loop
```

This installs the `ralph` command globally. If you don't have pipx, [install it first](https://pipx.pypa.io/stable/installation/) or use `pip install ralph-loop` in a virtual environment.

## Your First Project

### 1. Initialize Ralph

Navigate to your project directory and run:

```bash
ralph init
```

This creates:
- `.ralph/` directory (Ralph's state files)
- `PROMPT.md` template (where you describe your goal)

### 2. Edit PROMPT.md

Open `PROMPT.md` and describe what you want built. Here's a simple example:

```markdown
# Goal

Add a "Hello World" endpoint to the Flask app.

# Success Criteria

- [ ] GET /hello returns "Hello World"
- [ ] Response status is 200
- [ ] Endpoint is tested
```

The success criteria are important - Ralph uses them to know when the task is complete.

### 3. Run Ralph

```bash
ralph run
```

Ralph will:
1. Start Claude working on your task
2. Save progress after each chunk of work
3. Start fresh sessions as needed
4. Verify completion 3 times before finishing

You'll see output like:

```
RALPH  Supervising Claude...

[1/20] Working...
  Signal: CONTINUE
  Files changed: 3

[2/20] Working...
  Signal: DONE
  Files changed: 0 (1/3 verification)

...

Goal achieved in 4 rotations (2m 15s)
```

## What Just Happened?

Ralph ran Claude in a loop:

1. Claude worked on your task
2. When Claude's context got full (or it said "done"), Ralph saved the state
3. A fresh Claude session picked up where the last left off
4. When Claude said "done" 3 times with no changes, Ralph confirmed completion

This approach prevents context pollution and catches premature "done" declarations.

[Learn more about how Ralph works](./how-it-works.md)

## Next Steps

- [Write better prompts](./writing-prompts.md) - Get more reliable results
- [See examples](./examples/index.md) - Real PROMPT.md files for common tasks
- [Command reference](./commands/index.md) - All Ralph commands and options
- [Troubleshooting](./troubleshooting/index.md) - When things go wrong

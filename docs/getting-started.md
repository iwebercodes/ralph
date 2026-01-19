# Getting Started

Get from zero to your first successful Ralph run in under 5 minutes.

## Prerequisites

Before you start, you need:

- **Python 3.10 or higher** - Check with `python --version`
- **At least one AI agent CLI** - Claude CLI, Codex CLI, or both

### Supported AI Agents

Ralph works with multiple AI agent CLIs. Install at least one:

**Claude CLI** (from Anthropic):
- Download from [claude.ai/download](https://claude.ai/download)
- Verify: `claude --version`

**Codex CLI** (from OpenAI):
- Install from [github.com/openai/codex](https://github.com/openai/codex)
- Verify: `codex --version`

If you have both installed, Ralph uses them all and automatically rotates between them when one becomes rate limited. See [Agents](./concepts/agents.md) for details.

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
1. Start an AI agent working on your task
2. Save progress after each chunk of work
3. Start fresh sessions as needed
4. Verify completion 3 times before finishing

You'll see output like:

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

...

  ╭───────────────────────────────────────────────────────╮
  │  ✓ COMPLETE                                           │
  │  Goal achieved after 4 iterations (3/3 verified)      │
  │  Time: 2m 15s                                         │
  ╰───────────────────────────────────────────────────────╯
```

## What Just Happened?

Ralph ran your AI agent in a loop:

1. The agent worked on your task
2. When the agent's context got full (or it said "done"), Ralph saved the state
3. A fresh session picked up where the last left off
4. When the agent said "done" 3 times with no changes, Ralph confirmed completion

This approach prevents context pollution and catches premature "done" declarations.

[Learn more about how Ralph works](./how-it-works.md)

## Using Ralph with AI Agents

If you're using Ralph inside an AI coding agent (Claude Code, Codex, etc.), run:

```bash
ralph --about
```

This prints a comprehensive explanation of how to use Ralph that the agent can read and understand, including commands, options, and exit codes.

## Next Steps

- [Write better prompts](./writing-prompts.md) - Get more reliable results
- [See examples](./examples/index.md) - Real PROMPT.md files for common tasks
- [Command reference](./commands/index.md) - All Ralph commands and options
- [Troubleshooting](./troubleshooting/index.md) - When things go wrong

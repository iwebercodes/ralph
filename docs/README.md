# Ralph Documentation

Ralph supervises your AI coding agent to actually finish what it starts.

## Quick Navigation

**Just getting started?**
[Get up and running in 5 minutes](./getting-started.md)

**Something went wrong?**
[Troubleshooting guide](./troubleshooting/index.md)

**Need examples?**
[See real PROMPT.md examples](./examples/index.md)

**Looking up a command?**
[Command reference](./commands/index.md)

**Want to understand how it works?**
[How Ralph works](./how-it-works.md)

## In a Hurry?

```bash
pipx install ralph-loop
ralph init
# Edit PROMPT.md with your goal
ralph run
```

That's it. Ralph will keep Claude working until your goal is complete, verified 3 times.

## What is Ralph?

When you give Claude Code a complex task, it can lose context, forget decisions, or declare "done" too early. Ralph fixes this by breaking work into fresh-context chunks and maintaining state between them.

Ralph is for anyone who:
- Uses AI coding agents to build projects
- Gets frustrated when agents lose track of what they're doing
- Wants reliable completion without constant supervision

[Learn more about how Ralph works](./how-it-works.md)

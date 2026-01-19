# Rotations

A rotation is one agent session in Ralph's loop. Understanding rotations helps you understand how Ralph maintains quality over long tasks.

## What is a Rotation?

Each time Ralph calls an agent, that's one rotation. The agent works on the task, makes progress, and signals when done or ready for a fresh start.

Think of it like shifts at work:
- Worker 1 does their part, writes notes for the next person
- Worker 2 reads the notes, continues from where Worker 1 left off
- Each shift starts fresh but builds on previous work

## Why Rotate?

AI context windows get "polluted" over long conversations:
- Earlier decisions get pushed out of working memory
- Contradictory information accumulates
- The model starts making mistakes or forgetting things

Ralph prevents this by starting fresh regularly. Each rotation gets a clean context with:
- The original goal (PROMPT.md)
- Current progress (handoff.md)
- Learned lessons (guardrails.md)

No conversation history. No accumulated confusion.

## What Happens Each Rotation

1. **Ralph picks an agent** from the available pool
2. **Ralph builds a prompt** from your PROMPT.md plus current state
3. **Agent receives the prompt** with fresh context
4. **Agent works** on the task
5. **Agent updates handoff.md** with progress and notes
6. **Agent signals status** (CONTINUE, DONE, ROTATE, STUCK)
7. **Ralph logs the rotation** to history
8. **Next rotation begins** (if needed)

## Iteration vs Rotation

These terms mean the same thing. The code uses "iteration" but the concept is clearer as "rotation" - each turn of the loop.

## Viewing Rotations

See what happened in each rotation:

```bash
# List all rotations
ralph history --list

# View specific rotation
ralph history 3

# View most recent
ralph history
```

## Controlling Rotations

**Max iterations:** Limit how many rotations before stopping:
```bash
ralph run --max 30
```

**Manual rotation:** An agent can signal ROTATE when it wants a fresh context before hitting limits.

## Related

- [Agents](./agents.md) - The AI agents that run in rotations
- [Handoff](./handoff.md) - What persists between rotations
- [Status signals](./status-signals.md) - How agents control the loop
- [How it works](../how-it-works.md) - The big picture

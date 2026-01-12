# Rotations

A rotation is one Claude session in Ralph's loop. Understanding rotations helps you understand how Ralph maintains quality over long tasks.

## What is a Rotation?

Each time Ralph calls Claude, that's one rotation. Claude works on the task, makes progress, and signals when done or ready for a fresh start.

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

1. **Ralph builds a prompt** from your PROMPT.md plus current state
2. **Claude receives the prompt** with fresh context
3. **Claude works** on the task
4. **Claude updates handoff.md** with progress and notes
5. **Claude signals status** (CONTINUE, DONE, ROTATE, STUCK)
6. **Ralph logs the rotation** to history
7. **Next rotation begins** (if needed)

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

**Manual rotation:** Claude can signal ROTATE when it wants a fresh context before hitting limits.

## Related

- [Handoff](./handoff.md) - What persists between rotations
- [Status signals](./status-signals.md) - How Claude controls the loop
- [How it works](../how-it-works.md) - The big picture

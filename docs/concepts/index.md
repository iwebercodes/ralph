# Concepts

Ralph uses a few core concepts. Understanding them helps you use Ralph effectively and debug issues when they occur.

## Key Concepts

**[Rotations](./rotations.md)**
Each fresh Claude session in the loop. Ralph breaks work into rotations to keep context clean.

**[Verification](./verification.md)**
The 3x completion check. Ralph doesn't trust the first "done" - it verifies three times with no changes.

**[Handoff](./handoff.md)**
How state persists between rotations. The handoff.md file carries progress forward.

**[Guardrails](./guardrails.md)**
Lessons Claude learns while working. These persist across rotations to prevent repeated mistakes.

**[Status Signals](./status-signals.md)**
How Claude tells Ralph what to do next: CONTINUE, ROTATE, DONE, or STUCK.

## How They Fit Together

```
                    ┌─────────────┐
                    │  PROMPT.md  │  (your goal)
                    └──────┬──────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
   ┌─────────┐       ┌─────────┐       ┌─────────┐
   │Rotation │──────▶│Rotation │──────▶│Rotation │
   │    1    │       │    2    │       │    3    │
   └────┬────┘       └────┬────┘       └────┬────┘
        │                 │                 │
        ▼                 ▼                 ▼
   ┌─────────┐       ┌─────────┐       ┌─────────┐
   │handoff  │       │handoff  │       │ DONE    │
   │guardrails       │guardrails       │(verify) │
   └─────────┘       └─────────┘       └─────────┘
```

Each rotation:
1. Reads the current handoff and guardrails
2. Works toward the goal
3. Updates handoff with progress
4. Adds any lessons to guardrails
5. Signals status (CONTINUE, DONE, etc.)

## Next Steps

- [Getting started](../getting-started.md) - Install and run Ralph
- [How it works](../how-it-works.md) - The big picture

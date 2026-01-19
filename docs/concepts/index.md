# Concepts

Ralph uses a few core concepts. Understanding them helps you use Ralph effectively and debug issues when they occur.

## Key Concepts

**[Agents](./agents.md)**
The AI coding agents Ralph works with (Claude, Codex, etc.). Ralph manages them in a pool and rotates between them.

**[Rotations](./rotations.md)**
Each fresh agent session in the loop. Ralph breaks work into rotations to keep context clean.

**[Verification](./verification.md)**
The 3x completion check. Ralph doesn't trust the first "done" - it verifies three times with no changes.

**[Handoff](./handoff.md)**
How state persists between rotations. The handoff.md file carries progress forward.

**[Guardrails](./guardrails.md)**
Lessons agents learn while working. These persist across rotations to prevent repeated mistakes.

**[Status Signals](./status-signals.md)**
How agents tell Ralph what to do next: CONTINUE, ROTATE, DONE, or STUCK.

## How They Fit Together

```
                    ┌─────────────┐
                    │  PROMPT.md  │  (your goal)
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ Agent Pool  │  (Claude, Codex, etc.)
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

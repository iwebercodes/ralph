# How Ralph Works

Understanding Ralph helps you use it better. This page explains the core concept.

## The Problem

AI coding agents like Claude Code are powerful, but on larger tasks they can:

- **Lose context** - As conversations grow, earlier decisions get pushed out
- **Forget decisions** - What was agreed 50 messages ago may be ignored now
- **Declare "done" too early** - Agents often claim completion when work remains

You've probably experienced this: you ask for a feature, Claude works on it, says "done!", and you find half the requirements missing.

## Ralph's Solution

Ralph breaks big tasks into **fresh-context chunks**. Instead of one long conversation that degrades, you get many short focused sessions that stay sharp.

Here's what happens:

```
┌─────────────┐
│  PROMPT.md  │  Your goal and success criteria
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Rotation 1 │  Claude works, makes progress
│  (fresh)    │  Saves state to handoff.md
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Rotation 2 │  New Claude session reads handoff
│  (fresh)    │  Continues where R1 left off
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Rotation 3 │  Claude says "DONE"
│  (fresh)    │  Ralph checks: did files change?
└──────┬──────┘
       │
       ▼
   Verification (3x)
       │
       ▼
   Complete!
```

## The Verification

Agents often say "done" when they're not. Ralph doesn't trust the first "done" - or the second.

When Claude signals DONE:

1. Ralph checks if any files changed since the previous rotation
2. If files changed: Claude wasn't really done, keep working
3. If no files changed: count as one verification pass
4. After 3 consecutive "done" signals with no changes: truly complete

This catches:
- Premature completion claims
- Forgotten requirements
- Last-minute changes that were overlooked

## The Tradeoff

Ralph uses more tokens than running Claude directly:
- Each rotation is a fresh API call
- Verification adds extra rotations
- The state handoff takes tokens

**But:** You spend less time debugging, re-prompting, and cleaning up half-finished work. For complex tasks, the reliability is worth the extra cost.

## Key Concepts

Ralph has a few core concepts that help you understand what's happening:

- [Rotations](./concepts/rotations.md) - Individual Claude sessions in the loop
- [Verification](./concepts/verification.md) - The 3x completion check
- [Handoff](./concepts/handoff.md) - How state persists between rotations
- [Guardrails](./concepts/guardrails.md) - Lessons Claude learns as it works
- [Status Signals](./concepts/status-signals.md) - How Claude tells Ralph what to do

## Next Steps

- [Get started](./getting-started.md) - Install and run Ralph
- [Write better prompts](./writing-prompts.md) - Get more reliable results
- [See examples](./examples/index.md) - Real tasks and PROMPT.md files

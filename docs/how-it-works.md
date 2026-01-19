# How Ralph Works

Understanding Ralph helps you use it better. This page explains the core concept.

## The Problem

AI coding agents are powerful, but on larger tasks they can:

- **Lose context** - As conversations grow, earlier decisions get pushed out
- **Forget decisions** - What was agreed 50 messages ago may be ignored now
- **Declare "done" too early** - Agents often claim completion when work remains

You've probably experienced this: you ask for a feature, the agent works on it, says "done!", and you find half the requirements missing.

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
│  Rotation 1 │  Agent works, makes progress
│  (fresh)    │  Saves state to handoff.md
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Rotation 2 │  Fresh agent session reads handoff
│  (fresh)    │  Continues where R1 left off
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Rotation 3 │  Agent says "DONE"
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

When an agent signals DONE:

1. Ralph checks if any files changed since the previous rotation
2. If files changed: the agent wasn't really done, keep working
3. If no files changed: count as one verification pass
4. After 3 consecutive "done" signals with no changes: truly complete

This catches:
- Premature completion claims
- Forgotten requirements
- Last-minute changes that were overlooked

## The Tradeoff

Ralph uses more tokens than running an agent directly:
- Each rotation is a fresh API call
- Verification adds extra rotations
- The state handoff takes tokens

**But:** You spend less time debugging, re-prompting, and cleaning up half-finished work. For complex tasks, the reliability is worth the extra cost.

## Multi-Agent Support

Ralph works with multiple AI agents (Claude, Codex, etc.) and manages them in a pool:

- At startup, Ralph discovers which agent CLIs are installed
- During execution, it randomly selects an available agent for each rotation
- If an agent becomes exhausted (rate limited), Ralph removes it from the pool and continues with the remaining agents
- If all agents are exhausted, Ralph pauses until rate limits reset

This means you get more uptime and fewer interruptions. See [Agents](./concepts/agents.md) for details.

## Key Concepts

Ralph has a few core concepts that help you understand what's happening:

- [Agents](./concepts/agents.md) - The AI agents Ralph works with
- [Rotations](./concepts/rotations.md) - Individual agent sessions in the loop
- [Verification](./concepts/verification.md) - The 3x completion check
- [Handoff](./concepts/handoff.md) - How state persists between rotations
- [Guardrails](./concepts/guardrails.md) - Lessons agents learn as they work
- [Status Signals](./concepts/status-signals.md) - How agents tell Ralph what to do

## Next Steps

- [Get started](./getting-started.md) - Install and run Ralph
- [Write better prompts](./writing-prompts.md) - Get more reliable results
- [See examples](./examples/index.md) - Real tasks and PROMPT.md files

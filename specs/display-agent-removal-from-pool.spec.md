# Display agent removal from pool

## Goal

Following behaviour must be confirmed in source code, then manually verified. Missing functionality or found bugs must be fixed.

## Problem

When an agent is removed from the pool during runtime (due to rate limiting, quota exceeded, etc.), this happens silently. The user has no visibility into:
- Which agent was removed
- Why it was removed
- How many agents remain in the pool

This makes debugging difficult when Ralph suddenly stops using one of the configured agents.

## Desired Behavior

After a rotation completes, if the agent was removed from the pool, display a warning line inside the iteration box showing:
- Which agent was removed
- The reason for removal (extracted from the exhaustion pattern that matched)

### TTY Output (inside the iteration box)

```
  ├── Rotation complete ────────────────────────────────┤
  │  Result:       ROTATE                               │
  │  Files:        3 files changed                      │
  │  Agent:        Codex removed (rate limit)           │  ← NEW LINE
  ╰─────────────────────────────────────────────────────╯
```

The "Agent:" line should be yellow to indicate a warning.

### Non-TTY Output

```
[ralph] Result: ROTATE (3 files changed)
[ralph] Agent removed: Codex (rate limit)
```

## Test Cases

1. **Agent removed mid-run**: Start with Claude + Codex, trigger rate limit on one → should see removal message
2. **Multiple agents removed**: Both agents hit limits → should see both removal messages before "all agents exhausted"
3. **Non-TTY mode**: Verify plain text format works correctly
4. **No removal**: Normal run without exhaustion → no agent removal line shown

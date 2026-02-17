# Display rotation timing

## Goal

Following behaviour must be confirmed in source code, then manually verified. Missing functionality or found bugs must be fixed.

## Problem

When rotations complete, there's no visibility into how long each rotation took. This makes it difficult to:
- Identify performance issues where simple specs take unusually long
- Understand which specs are consuming the most time
- Detect agent performance degradation

## Desired Behavior

After a rotation completes, display the elapsed time inside the iteration box showing:
- Human-readable duration (e.g., "2m 13s" instead of "133 seconds")
- Consistent formatting that handles various time ranges appropriately

### TTY Output (inside the iteration box)

```
  ├── Rotation complete ────────────────────────────────┤
  │  Result:       DONE                                 │
  │  Files:        3 files changed                      │
  │  Time:         2m 13s                               │  ← NEW LINE
  │  Verification: 1/3 [●○○]                            │
  ╰─────────────────────────────────────────────────────╯
```

The "Time:" line should appear after "Files:" and before any agent removal or verification lines.

### Non-TTY Output

```
[ralph] Result: DONE (3 files changed)
[ralph] Time: 2m 13s
[ralph] Verification: 1/3 [●○○]
```

## Time Formatting Rules

- Under 60 seconds: Show as "Xs" (e.g., "45s")
- 60 seconds to 59 minutes: Show as "XmYs" (e.g., "2m 13s", "10m 0s")
- 60 minutes or more: Show as "XhYmZs" (e.g., "1h 13m 30s", "2h 0m 0s")
- Always show whole seconds (no decimals)
- Always include units even for zero values in compound times (e.g., "2h 0m 15s" not "2h 15s")

## Test Cases

1. **Quick rotation (< 1 minute)**: 45 second rotation → should show "45s"
2. **Medium rotation (few minutes)**: 133 second rotation → should show "2m 13s"
3. **Long rotation (over an hour)**: 4430 second rotation → should show "1h 13m 50s"
4. **Exact boundaries**: 60s → "1m 0s", 3600s → "1h 0m 0s"
5. **Non-TTY mode**: Verify plain text format includes timing
6. **Multiple rotations**: Each rotation shows its own accurate timing
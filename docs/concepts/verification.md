# Verification

Ralph doesn't trust the first "done" from Claude. Or the second. Verification ensures tasks are actually complete.

## Why Verify?

AI agents often declare "done" prematurely:
- They think they've addressed everything
- They overlook edge cases
- They forget requirements from earlier in the conversation

In normal use, you'd check the work yourself and point out what's missing. Ralph automates this with multiple verification passes.

## How It Works

When Claude signals DONE:

1. **Ralph checks:** Did any files change since last rotation?
2. **If files changed:** Claude wasn't done. Continue working.
3. **If no files changed:** Count as one verification pass.
4. **After 3 passes with no changes:** Task is truly complete.

```
Rotation 5: Signal DONE, 2 files changed
  → Not done, still making changes

Rotation 6: Signal DONE, 0 files changed
  → Verification 1/3

Rotation 7: Signal DONE, 0 files changed
  → Verification 2/3

Rotation 8: Signal DONE, 0 files changed
  → Verification 3/3 - Complete!
```

## What the Verification Catches

**Last-minute changes:** Claude sometimes remembers something at the end and makes quick fixes. If it's still changing things, it's not done.

**Premature completion:** When Claude says "done" but hasn't actually finished, subsequent rotations will make more changes (resetting verification).

**Overlooked requirements:** Fresh eyes in each rotation may catch things previous rotations missed.

## Seeing Verification Progress

In the output:
```
[6/20] Working...
  Signal: DONE
  Files changed: 0 (1/3 verification)
```

Or check status:
```bash
ralph status
```
```
  Done count: 2 / 3
```

## If Verification Takes Too Long

If Ralph keeps resetting verification (because files keep changing), the task may be:

- **Too vague:** Success criteria aren't clear enough
- **Scope creeping:** Claude keeps adding "improvements"
- **Unstable:** Something external is changing files

See [Task not finishing](../troubleshooting/not-finishing.md) for solutions.

## Related

- [Status signals](./status-signals.md) - The DONE signal and others
- [How it works](../how-it-works.md) - Where verification fits in the loop
- [Troubleshooting](../troubleshooting/not-finishing.md) - When verification won't complete

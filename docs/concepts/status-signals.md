# Status Signals

Status signals tell Ralph what to do next. Claude writes a signal at the end of each rotation.

## The Four Signals

| Signal | Meaning | What Ralph Does |
|--------|---------|-----------------|
| **CONTINUE** | More work to do | Start next rotation |
| **ROTATE** | Want fresh context | Start next rotation |
| **DONE** | Task complete | Check verification (3x needed) |
| **STUCK** | Need human help | Stop and ask for help |

## CONTINUE

Claude signals CONTINUE when there's more work to do but the context is still usable.

```
[3/20] Working...
  Signal: CONTINUE
  Files changed: 4
```

Ralph starts another rotation. The loop continues.

## ROTATE

Claude signals ROTATE when it wants a fresh context before hitting limits. Maybe the conversation is getting long or confusing.

```
[5/20] Working...
  Signal: ROTATE
  Files changed: 2
```

Ralph starts another rotation. Similar to CONTINUE but explicitly requests fresh context.

## DONE

Claude signals DONE when it believes the task is complete. Ralph doesn't trust this immediately.

```
[7/20] Working...
  Signal: DONE
  Files changed: 0 (1/3 verification)
```

Ralph checks if files changed:
- If files changed: Claude wasn't done, continue working
- If no files changed: Count toward verification
- After 3 DONEs with no changes: Task truly complete

See [Verification](./verification.md) for details.

## STUCK

Claude signals STUCK when it genuinely needs human help. Something is blocking progress.

```
[4/20] Working...
  Signal: STUCK

Ralph stopped. Claude needs help.
Check .ralph/handoff.md for details.
```

Ralph stops and returns exit code 2. Check handoff.md for what Claude needs.

See [Troubleshooting STUCK](../troubleshooting/ralph-stuck.md) for solutions.

## How Claude Signals

Claude writes the signal to `.ralph/status`:

```
DONE
```

You can check the current signal:
```bash
cat .ralph/status
```

Or use:
```bash
ralph status
```

## The Initial State

When Ralph initializes, status is IDLE - no signal yet.

## Related

- [Verification](./verification.md) - How DONE signals are verified
- [Troubleshooting STUCK](../troubleshooting/ralph-stuck.md) - When Claude needs help
- [ralph status](../commands/status.md) - Checking the current signal

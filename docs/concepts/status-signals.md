# Status Signals

Status signals tell Ralph what to do next. The agent writes a signal at the end of each rotation.

## The Four Signals

| Signal | Meaning | What Ralph Does |
|--------|---------|-----------------|
| **CONTINUE** | More work to do | Start next rotation |
| **ROTATE** | Want fresh context | Start next rotation |
| **DONE** | Task complete | Check verification (3x needed) |
| **STUCK** | Need human help | Stop and ask for help |

## CONTINUE

The agent signals CONTINUE when there's more work to do but the context is still usable.

```
  ╭── Claude working... ──────────────────────────────────╮
  │  Iteration:    3/20                                   │
  ├── Rotation complete ──────────────────────────────────┤
  │  Result:       CONTINUE                               │
  │  Files:        4 files changed                        │
  ╰───────────────────────────────────────────────────────╯
```

Ralph starts another rotation. The loop continues.

## ROTATE

The agent signals ROTATE when it wants a fresh context before hitting limits. Maybe the conversation is getting long or confusing.

```
  ╭── Codex working... ───────────────────────────────────╮
  │  Iteration:    5/20                                   │
  ├── Rotation complete ──────────────────────────────────┤
  │  Result:       ROTATE                                 │
  │  Files:        2 files changed                        │
  ╰───────────────────────────────────────────────────────╯
```

Ralph starts another rotation. Similar to CONTINUE but explicitly requests fresh context.

## DONE

The agent signals DONE when it believes the task is complete. Ralph doesn't trust this immediately.

```
  ╭── Claude reviewing... ────────────────────────────────╮
  │  Iteration:    7/20 [REVIEW]                          │
  ├── Rotation complete ──────────────────────────────────┤
  │  Result:       DONE                                   │
  │  Files:        no changes                             │
  │  Verification: 1/3 [●○○]                              │
  ╰───────────────────────────────────────────────────────╯
```

Ralph checks if files changed:
- If files changed: the agent wasn't done, continue working
- If no files changed: Count toward verification
- After 3 DONEs with no changes: Task truly complete

See [Verification](./verification.md) for details.

## STUCK

The agent signals STUCK when it genuinely needs human help. Something is blocking progress.

```
  ╭── Claude working... ──────────────────────────────────╮
  │  Iteration:    4/20                                   │
  ├── Rotation complete ──────────────────────────────────┤
  │  Result:       STUCK                                  │
  │  Files:        no changes                             │
  ╰───────────────────────────────────────────────────────╯

  ╭───────────────────────────────────────────────────────╮
  │  ✗ BLOCKED                                            │
  │  Human input needed                                   │
  ╰───────────────────────────────────────────────────────╯
```

Ralph stops and returns exit code 2. Check handoff.md for what the agent needs.

See [Troubleshooting STUCK](../troubleshooting/ralph-stuck.md) for solutions.

## How Agents Signal

The agent writes the signal to `.ralph/status`:

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
- [Troubleshooting STUCK](../troubleshooting/ralph-stuck.md) - When an agent needs help
- [ralph status](../commands/status.md) - Checking the current signal

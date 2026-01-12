# Troubleshooting

When things go wrong, start here. Find your problem below.

## Quick Diagnosis

**"Ralph says STUCK"**
Claude needs human help. [See solutions](./ralph-stuck.md)

**"Hit maximum iterations"**
Task ran too long without completing. [See solutions](./max-iterations.md)

**"Task keeps not finishing"**
Rotations happen but work never completes. [See solutions](./not-finishing.md)

**"Claude CLI errors"**
Problems with the Claude command-line tool. [See solutions](./claude-errors.md)

## General Debugging Tips

### Check the handoff

The handoff shows what Claude thinks is happening:

```bash
cat .ralph/handoff.md
```

Look for:
- Is progress being tracked?
- Are the same items stuck "in progress"?
- Do the notes reveal any issues?

### Check the history

See what happened in recent rotations:

```bash
ralph history --list
```

Look for patterns:
- Is Claude making progress each rotation?
- Is the same work being repeated?
- What signals is Claude sending?

View a specific rotation for details:
```bash
ralph history 5
```

### Check your PROMPT.md

Many issues come from unclear prompts:
- Is the goal specific and focused?
- Are success criteria testable?
- Is there too much in one task?

See [Writing effective prompts](../writing-prompts.md).

### When in doubt, reset

Sometimes state gets corrupted. Start fresh:

```bash
ralph reset
# Edit PROMPT.md if needed
ralph run
```

Keep guardrails if they contain useful lessons:
```bash
ralph reset --keep-guardrails
```

## Still Stuck?

If none of the troubleshooting pages help:

1. Check if the issue is with Claude CLI itself (not Ralph)
2. Try a simpler task to verify Ralph is working
3. File an issue with:
   - Your PROMPT.md
   - Output from `ralph history --list`
   - What you expected vs what happened

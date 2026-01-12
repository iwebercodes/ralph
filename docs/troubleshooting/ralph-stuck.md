# Ralph Says STUCK

When Claude signals STUCK, it genuinely needs human help to continue.

## What STUCK Means

Claude has hit something it cannot resolve on its own:
- Missing information
- Ambiguous requirements
- External dependencies it cannot access
- Permission or access issues

This isn't a failure - it's Claude being honest about needing help.

## What to Do

### 1. Read the handoff

Claude explains what's blocking:

```bash
cat .ralph/handoff.md
```

Look in the "In Progress" or "Notes" section for the problem description.

### 2. Fix the issue

Based on what Claude says:
- Provide missing information in PROMPT.md
- Install missing dependencies
- Fix permissions or access
- Clarify ambiguous requirements

### 3. Resume

Once you've addressed the issue:

```bash
ralph run
```

Ralph continues from where it left off.

## Common Causes

### Missing dependencies

```
STUCK: Cannot run tests - pytest not installed
```

Fix:
```bash
pip install pytest
ralph run
```

### Ambiguous requirements

```
STUCK: Unclear whether login should use email or username
```

Fix: Update PROMPT.md with clearer requirements, then:
```bash
ralph run
```

### External service issues

```
STUCK: Cannot connect to database - connection refused
```

Fix: Start the database, check configuration, then:
```bash
ralph run
```

### File permission issues

```
STUCK: Cannot write to /etc/config - permission denied
```

Fix: Adjust permissions or change the approach, then:
```bash
ralph run
```

## Preventing STUCK

Write clearer prompts from the start:

- Include all necessary context
- Specify exact requirements (not "log in somehow" but "login with email and password")
- List what's already available (dependencies, services, configuration)
- Note any constraints

See [Writing effective prompts](../writing-prompts.md).

## If Claude Keeps Getting Stuck

If the same issue keeps causing STUCK:

1. Add it to guardrails so future rotations know:
   ```bash
   echo "NOTE: Database must be running on localhost:5432" >> .ralph/guardrails.md
   ```

2. Consider if the task is appropriate for AI automation

3. Break the task into smaller pieces that don't hit the blocker

## Related

- [Writing prompts](../writing-prompts.md) - Prevent STUCK with better prompts
- [Status signals](../concepts/status-signals.md) - Understanding STUCK
- [ralph run](../commands/run.md) - Resume after fixing

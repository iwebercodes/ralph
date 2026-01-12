# Hit Maximum Iterations

Ralph stops after a set number of rotations (default: 20) to prevent runaway loops.

## What This Means

The loop ran 20 times (or your `--max` value) without completing. Possible reasons:
- Task is too large
- Requirements are unclear
- Something is preventing completion
- Claude is going in circles

## What to Do

### 1. Check the pattern

```bash
ralph history --list
```

Look for:
- **Lots of CONTINUE:** Task is large but progressing
- **DONEs with file changes:** Verification keeps resetting
- **Same signals repeating:** Might be stuck in a loop

### 2. Check progress

```bash
ralph history
cat .ralph/handoff.md
```

Is real progress being made? Or is work being repeated?

### 3. Choose a solution

**If progress is being made (task is large):**
Increase the limit and continue:
```bash
ralph run --max 50
```

**If work is being repeated:**
The task may need to be smaller or clearer. Reset and improve the prompt:
```bash
ralph reset
# Edit PROMPT.md
ralph run
```

**If you're not sure:**
Look at several rotations to understand what's happening:
```bash
ralph history 15
ralph history 18
ralph history 20
```

## Preventing This

### Split large tasks

Instead of:
```markdown
# Goal
Build an entire user management system with auth, profiles, and admin panel.
```

Try:
```markdown
# Goal
Add user registration with email/password.
```

Then run separately for login, profiles, admin, etc.

### Write clearer criteria

Vague criteria cause endless work:
```markdown
# Bad
- [ ] Code is well-tested

# Good
- [ ] Unit tests cover all public functions
- [ ] Tests are in tests/ directory
- [ ] All tests pass
```

### Add constraints

Prevent scope creep:
```markdown
# Constraints
- Don't refactor existing code
- Keep changes under 200 lines
- Focus only on the login feature
```

## Checking if Complete

Even at max iterations, work may be done. Check:

```bash
ralph status
```

If done_count is 2/3 or 3/3, the task might be complete - it just ran out of iterations during verification.

Look at what was accomplished:
```bash
cat .ralph/handoff.md
```

## Related

- [Writing prompts](../writing-prompts.md) - Better prompts, faster completion
- [ralph run](../commands/run.md) - The --max option
- [ralph history](../commands/history.md) - Debug what happened

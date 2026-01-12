# Task Not Finishing

Rotations keep happening but the task never completes.

## Symptoms

- Many rotations but never hits DONE
- Keeps saying CONTINUE
- Verification resets (files keep changing on DONE)
- Progress in handoff doesn't match expectations

## Diagnose the Problem

### Check the pattern

```bash
ralph history --list
```

**Pattern: All CONTINUE, never DONE**
Claude thinks there's always more work. Check if success criteria are achievable.

**Pattern: DONE then file changes**
Claude says done but then makes changes. Verification keeps resetting.

**Pattern: Same work repeated**
Look at several rotations - is Claude doing the same thing over and over?

### Check progress

```bash
cat .ralph/handoff.md
```

- Is the "Completed" section growing?
- Is "In Progress" stuck on the same item?
- Do the notes reveal confusion?

### Check a few rotations

```bash
ralph history 5
ralph history 8
ralph history 10
```

Compare what Claude did. Is it making real progress?

## Common Causes

### Success criteria are unclear

```markdown
# Bad - what does "works well" mean?
- [ ] Authentication works well

# Good - testable
- [ ] POST /login returns JWT token
- [ ] JWT token expires after 24 hours
- [ ] Invalid credentials return 401
```

### Task is too large

One goal with 15 success criteria rarely finishes. Split it:

```markdown
# Goal
Add login endpoint.

# Success Criteria
- [ ] POST /login accepts email and password
- [ ] Returns JWT on success
- [ ] Returns 401 on invalid credentials
```

Then run again for registration, password reset, etc.

### Scope creep

Claude keeps finding "improvements" to make. Add constraints:

```markdown
# Constraints
- Don't refactor existing code
- Don't add features not in success criteria
- Focus only on what's listed above
```

### External state changing

Something outside Claude is changing files:
- Watch processes
- Auto-formatters
- Other tools

Check if files change between rotations without Claude's action.

## Solutions

### Rewrite the prompt

Be more specific:

```bash
ralph reset
# Edit PROMPT.md with clearer criteria
ralph run
```

### Add guardrails

If Claude keeps making the same mistake:

```bash
echo "RULE: Only modify files needed for the login feature" >> .ralph/guardrails.md
ralph run
```

### Split the task

Reset and do a smaller piece:

```bash
ralph reset
# Edit PROMPT.md with smaller scope
ralph run
```

### Manual intervention

Sometimes you need to help:

1. Read handoff.md to understand state
2. Fix something manually
3. Update handoff.md to reflect what you did
4. Run ralph again

## Related

- [Writing prompts](../writing-prompts.md) - Clearer prompts finish faster
- [Verification](../concepts/verification.md) - Why DONE keeps resetting
- [Guardrails](../concepts/guardrails.md) - Add rules to prevent loops

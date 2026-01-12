# Handoff

The handoff.md file is Ralph's memory between rotations. It carries progress, notes, and next steps from one Claude session to the next.

## What is Handoff?

Each rotation starts fresh - Claude has no memory of previous rotations. Handoff.md bridges this gap by providing:

- What's been completed
- What's in progress
- What to do next
- Important notes and decisions

## The Structure

```markdown
# Handoff

## Completed

- Implemented user model in src/models/user.py
- Added registration endpoint at POST /auth/register
- Created validation for email format

## In Progress

Working on login endpoint.

## Next Steps

1. Complete login endpoint with JWT generation
2. Add authentication middleware
3. Write tests for both endpoints

## Notes

- Using bcrypt for password hashing (already in requirements.txt)
- JWT secret is in environment variable JWT_SECRET
- Tests should use the test database configured in conftest.py
```

## How It Works

1. **Rotation starts:** Claude reads handoff.md to understand current state
2. **During work:** Claude makes progress on the task
3. **Before signaling:** Claude updates handoff.md with new progress
4. **Next rotation:** New Claude session reads the updated handoff

The handoff is the only way information persists between rotations (along with guardrails and actual file changes).

## Viewing the Handoff

The file is at `.ralph/handoff.md`:

```bash
cat .ralph/handoff.md
```

You can read it anytime to see what Claude thinks the current state is.

## If Handoff Gets Corrupted

Sometimes the handoff becomes confusing or inaccurate. Options:

**Edit it manually:** Fix specific issues in `.ralph/handoff.md`

**Reset and start over:**
```bash
ralph reset
```

This clears the handoff to the default template.

## Related

- [Rotations](./rotations.md) - What happens between handoffs
- [Guardrails](./guardrails.md) - The other persistent state
- [ralph reset](../commands/reset.md) - Clear the handoff

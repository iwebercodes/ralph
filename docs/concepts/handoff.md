# Handoff

Handoff files are Ralph's memory between rotations. Each spec gets its own handoff so
progress stays scoped to the active constraint.

## What is Handoff?

Each rotation starts fresh - the agent has no memory of previous rotations. The handoff bridges this gap by providing:

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

1. **Rotation starts:** The agent reads the current spec's handoff to understand state
2. **During work:** The agent makes progress on the task
3. **Before signaling:** The agent updates the handoff with new progress
4. **Next rotation:** A new agent session reads the updated handoff

The handoff is the only way information persists between rotations (along with guardrails and actual file changes).

## Viewing the Handoff

Handoffs live in `.ralph/handoffs/` with `{name}-{hash}.md` filenames:

```bash
ls .ralph/handoffs
```

You can read it anytime to see what the agent thinks the current state is.

## If Handoff Gets Corrupted

Sometimes the handoff becomes confusing or inaccurate. Options:

**Edit it manually:** Fix specific issues in the relevant file under `.ralph/handoffs/`

**Reset and start over:**
```bash
ralph reset
```

This clears handoffs to the default template.

## Related

- [Rotations](./rotations.md) - What happens between handoffs
- [Guardrails](./guardrails.md) - The other persistent state
- [ralph reset](../commands/reset.md) - Clear the handoff

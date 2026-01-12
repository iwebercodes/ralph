# Guardrails

Guardrails are lessons Claude learns while working. They persist across rotations to prevent repeated mistakes.

## What are Guardrails?

As Claude works, it may discover important constraints or patterns:

- "Tests must pass before signaling DONE"
- "The API uses camelCase, not snake_case"
- "Never modify files in vendor/ directory"

Instead of re-learning these each rotation, Claude writes them to guardrails.md. Future rotations see and follow them.

## Example Guardrails

```markdown
# Guardrails

## Project Conventions
- Use TypeScript strict mode
- All API responses follow { data, error } format
- Tests are in __tests__/ directories next to source files

## Learned Lessons
- The database migration must run before tests
- Auth middleware is in src/middleware/auth.ts, not lib/
- Environment variables are loaded from .env.local in development
```

## How They Work

1. **Claude discovers something:** A pattern, constraint, or gotcha
2. **Claude adds it to guardrails.md:** Written as a clear rule
3. **Future rotations read it:** And follow the rule
4. **Mistakes aren't repeated:** Lessons persist

## Viewing Guardrails

The file is at `.ralph/guardrails.md`:

```bash
cat .ralph/guardrails.md
```

## Preserving Guardrails

When resetting for a new task, you often want to keep guardrails:

```bash
ralph reset --keep-guardrails
```

This clears progress but keeps lessons learned. Useful when:
- Starting a new task in the same project
- The lessons apply to future work
- You've accumulated valuable project knowledge

## When to Clear Guardrails

Clear guardrails when:
- Moving to a completely different project
- Guardrails have become outdated or wrong
- Starting fresh without any prior assumptions

```bash
ralph reset  # Clears everything including guardrails
```

## Adding Your Own Guardrails

You can edit `.ralph/guardrails.md` directly to add your own rules:

```markdown
# Guardrails

## My Rules
- Always run prettier before committing
- Don't modify the shared/ directory without discussion
- Tests must cover error cases, not just happy paths
```

Claude will follow these alongside any it discovers.

## Related

- [Handoff](./handoff.md) - The other persistent state
- [ralph reset](../commands/reset.md) - Clearing or keeping guardrails
- [Rotations](./rotations.md) - When guardrails get read

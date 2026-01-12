# Example: Refactoring Code

This example shows how to restructure code while maintaining functionality.

## The Task

Extract database logic from route handlers into a dedicated data access layer.

## The PROMPT.md

```markdown
# Goal

Extract database logic from Express route handlers into a separate data access layer.

# Current Problem

Route handlers in src/routes/ contain raw SQL queries mixed with HTTP logic. This makes testing hard and violates separation of concerns.

Example of current code (in src/routes/users.ts):
```javascript
router.get('/users/:id', async (req, res) => {
  const result = await db.query('SELECT * FROM users WHERE id = $1', [req.params.id]);
  if (!result.rows[0]) return res.status(404).json({ error: 'Not found' });
  res.json(result.rows[0]);
});
```

# Success Criteria

- [ ] Database queries are in src/db/repositories/
- [ ] Each entity has its own repository (users.ts, products.ts, orders.ts)
- [ ] Route handlers call repository methods, not raw queries
- [ ] No SQL strings in src/routes/ files
- [ ] All existing tests still pass
- [ ] Repository methods are typed with TypeScript

# Desired Structure

```
src/
├── db/
│   └── repositories/
│       ├── users.ts      # UserRepository
│       ├── products.ts   # ProductRepository
│       └── orders.ts     # OrderRepository
├── routes/
│   ├── users.ts          # Calls UserRepository
│   ├── products.ts
│   └── orders.ts
```

# Context

- Express app with PostgreSQL
- Using pg library for database (not an ORM)
- TypeScript with strict mode
- Current entities: users, products, orders

# Constraints

- Don't change the database schema
- Don't change the API responses (same data format)
- Don't add new dependencies
- Existing tests must keep passing without modification
```

## Why This Works

**Clear before/after:** Shows what exists and what should exist.

**Specific structure:** The desired directory layout is explicit.

**Strong constraints:**
- "Don't change API responses" - behavior stays same
- "Existing tests must pass" - proves nothing broke
- "No SQL in routes" - clear rule to verify

**Scoped properly:** Just this refactor, not adding features or changing APIs.

## Running It

```bash
ralph init
# Paste the PROMPT.md above
ralph run
```

Expected flow:
1. Claude reads current route files
2. Creates repository directory structure
3. Extracts queries into repositories
4. Updates routes to use repositories
5. Runs tests to verify nothing broke
6. Signals DONE

## Key Refactoring Patterns

**Include "before" examples:** Show Claude what the current code looks like.

**Define the end state:** What should the structure be when done?

**Test as guardrail:** "Existing tests must pass" ensures behavior is preserved.

**No scope creep:** Refactoring should change structure, not behavior.

## Adapting This Example

For your own refactoring:

1. **Show the problem** - what's wrong with current structure?
2. **Define the target** - what should it look like after?
3. **List what moves where** - be specific about the restructure
4. **Set behavior constraints** - "API stays the same", "tests pass"
5. **Exclude other changes** - no features, no fixes, just restructure

## Related

- [Writing prompts](../writing-prompts.md) - More on effective prompts
- [Add feature example](./add-feature.md) - New functionality
- [Fix bug example](./fix-bug.md) - Bug fixes

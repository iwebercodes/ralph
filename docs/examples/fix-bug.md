# Example: Fixing a Bug

This example shows how to fix a specific bug with clear reproduction steps.

## The Task

Fix a bug where the shopping cart shows incorrect totals after removing items.

## The PROMPT.md

```markdown
# Goal

Fix the cart total calculation bug when items are removed.

# Bug Description

When removing an item from the shopping cart, the total doesn't update correctly.

**Steps to reproduce:**
1. Add 3 items to cart ($10, $20, $30 = $60 total)
2. Remove the $20 item
3. Total still shows $60 instead of $40

**Expected:** Total updates to reflect remaining items ($40)
**Actual:** Total stays at previous value ($60)

# Success Criteria

- [ ] Removing an item updates the total immediately
- [ ] Total is correct after removing any item
- [ ] Total is correct after removing all items (shows $0 or empty state)
- [ ] Existing tests still pass
- [ ] New test covers the remove-and-recalculate case

# Context

- Cart logic is in src/hooks/useCart.ts
- Cart component is src/components/Cart.tsx
- Tests are in src/hooks/__tests__/useCart.test.ts
- Using React with Context for state management

# Constraints

- Don't refactor the cart beyond fixing this bug
- Keep the fix minimal
- Add only one test for this specific case
```

## Why This Works

**Clear reproduction:** Not "cart is broken" but exact steps to see the problem.

**Expected vs actual:** Makes the bug unambiguous.

**Focused criteria:**
- Fix the specific problem
- Don't break existing functionality
- Add a test to prevent regression

**Located context:** Claude knows exactly where to look:
- The hook that needs fixing
- The component that uses it
- Where tests live

**Bounded scope:** "Don't refactor beyond fixing this bug" prevents Claude from rewriting the whole cart system.

## Running It

```bash
ralph init
# Paste the PROMPT.md above
ralph run
```

Expected flow:
1. Claude reads the cart hook code
2. Identifies the calculation issue
3. Fixes the logic
4. Adds a test
5. Verifies existing tests pass
6. Signals DONE

## Adapting This Example

For your own bug fix:

1. **Describe reproduction steps** - be specific
2. **State expected vs actual** - what should happen?
3. **Keep criteria focused** - fix the bug, add a test
4. **Point to files** - where's the bug likely to be?
5. **Bound the scope** - "fix this, don't refactor everything"

## When Bugs Are Harder to Find

If you don't know where the bug is:

```markdown
# Goal

Find and fix why user sessions expire randomly.

# Bug Description

Users report being logged out unexpectedly. No clear pattern found yet.

**What we know:**
- Happens 2-3 times per day
- No errors in logs
- Session should last 24 hours

# Success Criteria

- [ ] Root cause identified and documented
- [ ] Bug is fixed
- [ ] Test added to prevent regression
- [ ] Explain the fix in handoff notes
```

This gives Claude license to investigate rather than just fix.

## Related

- [Writing prompts](../writing-prompts.md) - More on effective prompts
- [Add feature example](./add-feature.md) - New functionality
- [Refactor example](./refactor.md) - Code restructuring

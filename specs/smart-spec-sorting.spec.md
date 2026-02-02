# Smart Spec Sorting

Prioritize specs that are more likely to produce changes over specs that are already done.

## Problem

When running ralph with many specs, iterating through specs that repeatedly return DONE wastes time. A newly created spec or one that caused recent changes gets buried behind potentially hundreds of DONE specs. Every time a spec causes file changes, all other specs need to be re-evaluated, but most will still return DONE.

## Goal

Track the last processing state of each spec and sort specs so that active ones (not DONE) are processed first.

## Success Criteria

### State Persistence

- [ ] Save the last result state for each spec (DONE, ROTATE, CONTINUE, STUCK, etc.)
- [ ] State persists across ralph restarts
- [ ] New specs (no saved state) are treated as high priority

### Sorting Priority

- [ ] Specs with no saved state (new) are processed first
- [ ] Specs with non-DONE last state are processed before DONE specs
- [ ] Among specs with same priority, maintain stable ordering (e.g., alphabetical or by file modification time)

### State Reset

- [ ] When a spec causes file changes, other specs' states remain unchanged
- [ ] A spec's state updates only after it is processed
- [ ] `ralph reset` clears all spec states

### Automated Tests

- [ ] New specs are processed before DONE specs
- [ ] State persists across restarts
- [ ] Sorting stability within priority tiers
- [ ] `ralph reset` clears spec states

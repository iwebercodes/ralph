# Smart Spec Sorting

Prioritize specs that are more likely to produce changes over specs that are already done.

## Problem

When running ralph with many specs, iterating through specs that repeatedly return DONE wastes time. A newly created spec or one that caused recent changes gets buried behind potentially hundreds of DONE specs. Every time a spec causes file changes, all other specs need to be re-evaluated, but most will still return DONE.

## Goal

Track the last processing state of each spec and sort specs so that active ones (not DONE) are processed first.

## Success Criteria

### State Persistence

- [ ] Save the last result state for each spec (DONE, ROTATE, CONTINUE, STUCK, etc.)
- [ ] Save the hash for each spec to be able to recognize if a spec was changed
- [ ] State persists across ralph restarts

### Sorting Priority

- [ ] New specs (no saved state) are treated as highest priority (must come first)
- [ ] Modified specs come as second priority
- [ ] Specs that modified files but returned DONE are third priority
- [ ] Specs that didn't modify files and returned DONE are last priority (consedered less likely to produce any changes)
- [ ] Among specs with same priority, maintain stable ordering (e.g., alphabetical or by file modification time)

### State Reset

- [ ] When a spec causes file changes, other specs' states remain unchanged
- [ ] A spec's state updates only after it is processed
- [ ] `ralph reset` does NOT clear spec states

### Automated Tests

- [ ] Described behaviour is thoroughly tested with automated tests
- [ ] The tests cover positive and error paths, edge cases and give us high confidence it works as intendend

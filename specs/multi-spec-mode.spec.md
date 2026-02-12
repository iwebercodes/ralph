# Multi-Spec Mode

Ralph works on multiple spec files simultaneously, ensuring all constraints are satisfied without regressions.

## Problem

When working on multiple tasks sequentially, later work can break earlier achievements:

1. Create PROMPT.md, Ralph completes it
2. Create PROMPT-2.md, Ralph completes it but breaks success criteria from PROMPT.md
3. User must either write comprehensive tests or re-run Ralph with old prompts

## Solution

Treat multiple spec files as constraints that must ALL be satisfied simultaneously. Ralph focuses on one spec at a time until it reaches DONE with no file changes, then moves to the next highest priority spec. New specs always take precedence.

## Shared vs Per-Spec Resources

| Resource | Scope | Notes |
|----------|-------|-------|
| Handoff | Per spec | Each spec maintains its own handoff for agent continuity |
| Guardrails | Shared | Project-wide knowledge, agents can leave info for each other |
| History | Per spec | Track implementation journey for each spec individually |
| State | Shared | Single file containing the matrix of all specs and their progress |
| Snapshots | Shared | Same project files tracked regardless of active spec |
| current.log | Shared | One agent runs at a time |
| run.json | Shared | One Ralph instance |

## File Structure

Per-spec files use `{name}-{short_hash}` format to handle specs in subfolders (names may collide, paths won't):

```
.ralph/
  state.json                        # matrix of all specs
  guardrails.md                     # shared
  run.json                          # shared
  current.log                       # shared
  handoffs/
    000-prompt-a1b2c3.md            # PROMPT.md
    api.spec-d4e5f6.md              # specs/api.spec.md
    api.spec-g7h8i9.md              # specs/v2/api.spec.md
  history/
    000-prompt-a1b2c3/
      001.log
    api.spec-d4e5f6/
      001.log
      002.log
```

The hash is derived from the full relative path (6 hex chars).

## Success Criteria

### Spec Discovery

- [ ] Discover `PROMPT.md` in project root (if exists)
- [ ] Discover `*.spec.md` files in `.ralph/specs/` recursively
- [ ] Discover `*.spec.md` files in `./specs/` recursively
- [ ] Sort all specs alphabetically by full relative path during discovery
- [ ] Treat `PROMPT.md` as `000-prompt.spec.md` for sorting (always first)
- [ ] Works on Linux, macOS, and Windows

### Focused Execution

#### Core Execution Flow
- [ ] Work on one spec continuously until it reaches DONE with no file changes
- [ ] If a spec returns CONTINUE or ROTATE, keep working on the same spec in the next iteration
- [ ] Only switch to a different spec when current spec returns DONE with no file changes
- [ ] When switching after DONE with no changes, prefer other specs that need work over the current spec
- [ ] Only continue with the current spec if it's the only remaining spec that needs work (done_count < 3)
- [ ] Exception: If a new spec is discovered, immediately switch to it (highest priority)

#### Verification Progress
- [ ] Track progress per spec (0/3, 1/3, 2/3, 3/3) - see verification-counter-behavior.spec.md for details
- [ ] When a spec causes tracked file changes, reset that spec counter by its own result (DONE -> 1/3, non-DONE -> 0/3); for all other specs, only downgrade fully verified specs from 3/3 to 2/3 and leave 0/3, 1/3, 2/3 unchanged
- [ ] Complete when ALL specs reach 3/3 without file changes

#### Example Execution Sequence
1. Start with highest priority spec (e.g., new spec A)
2. Work on A until DONE with no changes (might take multiple iterations if CONTINUE/ROTATE)
3. Check for new specs - if found, switch to new spec immediately
4. Otherwise, select next highest priority spec (e.g., spec B with non-DONE status)
5. Work on B until DONE with no changes
6. Continue until all specs reach 3/3

### Smart Spec Prioritization

#### Between Iterations
- [ ] After each iteration completes, before selecting the next spec:
  - [ ] Re-scan all spec directories for changes
  - [ ] Detect newly added spec files
  - [ ] Detect removed spec files (update state.json accordingly)
  - [ ] Detect modified spec files (compare content hash)
  - [ ] Re-prioritize all specs based on current state
- [ ] If current spec is still highest priority (e.g., returned CONTINUE/ROTATE), continue with it
- [ ] If a higher priority spec exists (e.g., new spec added), switch to it immediately

#### Runtime Spec Selection
- [ ] New specs (not yet processed) always have highest priority and interrupt current work
- [ ] When current spec reaches DONE with no file changes, select next spec by priority:
  1. New specs (no saved state) - highest priority
  2. Modified specs (content hash changed)
  3. Non-DONE specs (CONTINUE, ROTATE, STUCK, etc.) or specs that previously changed files
  4. DONE specs that didn't modify tracked files - lowest priority
- [ ] Within priority tier 4 (DONE with no file changes), prefer lower verification count first (e.g., 1/3 before 2/3), then alphabetical by path as tie-breaker
- [ ] Within each tier, maintain stable ordering; use alphabetical by path unless a tier defines a more specific rule

#### On Restart
- [ ] Use the same priority order as runtime spec selection
- [ ] Resume from the highest priority spec

#### State Tracking
- [ ] Save the last result state for each spec (DONE, ROTATE, CONTINUE, STUCK, etc.)
- [ ] Save the content hash for each spec to detect modifications
- [ ] Track whether each spec modified files in its last rotation
- [ ] State persists across Ralph restarts

#### State Updates
- [ ] When a spec causes file changes, other specs' per-spec state remains unchanged (until processed), except verification counters where 3/3 specs downgrade to 2/3
- [ ] A spec's state updates only after it is processed
- [ ] `ralph reset` does NOT clear spec states (only resets counters and iteration)

### Per-Spec Resources

- [ ] Each spec has its own handoff file in `.ralph/handoffs/`
- [ ] Each spec has its own history directory in `.ralph/history/`
- [ ] Filename format: `{name}-{short_hash}` where hash is 6 hex chars from full path
- [ ] Guardrails remain shared (single `.ralph/guardrails.md`)

### State Management

- [ ] `state.json` tracks the full matrix of specs and their progress
- [ ] State includes: path, done_count, last_status, last_hash, modified_files flag
- [ ] State persists across Ralph restarts
- [ ] Spec changes are detected between iterations:
  - [ ] Adding new spec files triggers immediate reprioritization
  - [ ] Removing spec files updates the matrix (removed specs are dropped from state)
  - [ ] Modifying spec content is detected via hash comparison
- [ ] When spec list changes (added/removed), preserve state for existing unchanged specs

### UI

The existing panel gains a "Spec" row showing the current spec file:

```
╭── Codex reviewing... ───────────────────────────────────╮
│  Spec:         specs/api.spec.md                        │
│  Iteration:    7/20 [REVIEW]                            │
```

- [ ] Display panel shows `Spec: {filepath}` row for current spec
- [ ] Always shown, even with single PROMPT.md

### Backwards Compatibility

- [ ] Single `PROMPT.md` mode works exactly as before (matrix of one)
- [ ] No spec files = error with helpful message

### Automated Tests

- [ ] All described behaviors are thoroughly tested with automated tests
- [ ] Tests provide high confidence that the implementation works as specified

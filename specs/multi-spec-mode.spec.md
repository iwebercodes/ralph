# Multi-Spec Mode

Ralph works on multiple spec files simultaneously, ensuring all constraints are satisfied without regressions.

## Problem

When working on multiple tasks sequentially, later work can break earlier achievements:

1. Create PROMPT.md, Ralph completes it
2. Create PROMPT-2.md, Ralph completes it but breaks success criteria from PROMPT.md
3. User must either write comprehensive tests or re-run Ralph with old prompts

## Solution

Treat multiple spec files as constraints that must ALL be satisfied simultaneously. Ralph rotates through specs round-robin, resetting all progress counters whenever any tracked file changes.

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
- [ ] Sort all specs alphabetically by full relative path
- [ ] Treat `PROMPT.md` as `000-prompt.spec.md` for sorting (always first)
- [ ] Works on Linux, macOS, and Windows

### Round-Robin Execution

- [ ] Iterate through specs in order, one rotation per spec
- [ ] Track progress per spec (0/3, 1/3, 2/3, 3/3)
- [ ] Reset ALL spec counters when any tracked file changes
- [ ] Complete when ALL specs reach 3/3 without file changes

### Per-Spec Resources

- [ ] Each spec has its own handoff file in `.ralph/handoffs/`
- [ ] Each spec has its own history directory in `.ralph/history/`
- [ ] Filename format: `{name}-{short_hash}` where hash is 6 hex chars from full path
- [ ] Guardrails remain shared (single `.ralph/guardrails.md`)

### State Management

- [ ] `state.json` tracks the full matrix of specs and their progress
- [ ] State persists across Ralph restarts
- [ ] Adding/removing spec files is detected and matrix is updated

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

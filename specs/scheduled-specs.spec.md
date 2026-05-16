# System Specs (Periodic Every-N Execution)

Ralph supports a special spec file naming convention — `[name].every-[n].spec.md` — that creates a **system spec**. System specs are a distinct category from regular specs and operate under different rules: they fire on a schedule, run alongside (not instead of) regular specs, and are stateless from the loop's perspective.

## Problem

1. Large projects produce many output documents during processing; some grow too large and break downstream tools
2. Cleanup/consolidation work (e.g., "condense document X") is needed periodically, not every rotation
3. Currently the user must stop Ralph, run a separate cleanup script, then restart Ralph — breaking flow and losing context
4. Periodic tasks like format checks, consolidation, or linting don't need to run every single rotation — they should run on a schedule alongside regular work

## Goal

Add support for `[name].every-[n].spec.md` spec files that create **system specs**. On any iteration where `iteration % n == 0`, every eligible system spec fires **before** the regular spec phase of that iteration. System specs do not consume the iteration slot, do not write to state, do not write to handoff, and do not participate in the completion check. They can only persist effects via project files and guardrails.

## Architecture: Two Spec Categories

Ralph operates with two categories of specs:

### Regular Specs (default)
- No `.every-[n]` in filename (or `every_n == 1`)
- Follow the existing 0→3 verification cycle
- Tracked in `state.json`: `done_count`, `last_status`, `last_hash`, `modified_files`
- Goal achieved when all regular specs reach `done_count >= 3`

### System Specs (every-n)
- Have `.every-[n].spec.md` in filename where `n > 1`
- Fire on every n-th iteration (`iteration % n == 0`)
- Fire **before** the regular spec phase within the same iteration
- **Stateless**: no entry in `state.json`, no `done_count`, no `last_status`
- **MUST NOT** write to state or to handoff
- **MAY** write to guardrails (these are surfaced in subsequent prompts) and to any project file
- Have a dedicated prompt template (no `[IMPLEMENT]` / `[REVIEW]` markers)
- Completion signals (CONTINUE/ROTATE/DONE/STUCK) from a system spec are ignored by the loop — system specs do not write a status file
- Do **not** participate in the "all specs done" completion check

### Execution Model Per Iteration

Each loop turn:

```
1. Exit check: if no regular spec has work (all regulars at done_count >= 3,
   or no regular specs exist) → exit 0.
2. System spec phase: for every system spec where (iteration % n == 0),
   run it. Multiple system specs run sequentially in alphabetical order by
   relative path. File changes from a system spec count for the downgrade
   rule (any regular spec at 3/3 is downgraded to 2/3 — same rule as a
   regular spec causing file changes).
3. Regular spec phase: select the highest-priority eligible regular spec
   and run one turn.
4. Iteration counter += 1.
```

The exit check fires **before** the system phase. A system spec does not get one last run on the iteration where Ralph decides to exit.

Because there is always work to do in step 3 (otherwise step 1 would have exited), there are no no-op iterations.

```
Example with A.spec.md, B.spec.md (regular), every-2.spec.md, every-3.spec.md:

Iter 1: regulars not done → system: none → regular: A
Iter 2: regulars not done → system: every-2 → regular: A
Iter 3: regulars not done → system: every-3 → regular: A
Iter 4: regulars not done → system: every-2 → regular: A (reaches 3/3)
Iter 5: regulars not done (B 0/3) → system: none → regular: B
Iter 6: regulars not done → system: every-2, every-3 → regular: B
Iter 7: regulars not done → system: none → regular: B
Iter 8: regulars not done → system: every-2 → regular: B (reaches 3/3)
Iter 9: exit check: all regulars at 3/3 → exit 0. System specs do not run.
```

## Success Criteria

### File Naming and Discovery

- [ ] Ralph discovers `*.every-[n].spec.md` files alongside regular `*.spec.md` files
- [ ] The `every-[n]` portion must be a positive integer greater than 1 (e.g., `.every-3.spec.md`, `.every-10.spec.md`)
- [ ] Valid examples: `check-format-subpages.every-3.spec.md`, `consolidate-docs.every-5.spec.md`
- [ ] Invalid patterns are NOT treated as system specs and are discovered as regular `*.spec.md` files (e.g., `my.every.spec.md` is a normal spec, `.every-.spec.md` is a normal spec)
- [ ] System specs are discovered from the same locations as regular specs: `.ralph/specs/**/*.spec.md`, `specs/**/*.spec.md`

### Parsing the Schedule

- [ ] Extract the integer `n` from the filename pattern `[name].every-[n].spec.md`
- [ ] The name portion (before `.every-`) can contain any valid characters including dots, hyphens, underscores
- [ ] If a filename has multiple `.every-[n]` segments, use the **last** one (e.g., `a.every-2.b.every-3.spec.md` → n=3)
- [ ] `.every-0.spec.md` is NOT a system spec — treated as a regular spec
- [ ] `.every-1.spec.md` is NOT a system spec — treated as a regular spec (period of 1 is meaningless)
- [ ] `.every-abc.spec.md` is NOT a system spec — treated as a regular spec
- [ ] Files with no valid `every-[n]` pattern are regular specs

### System Spec Execution Rules

- [ ] A system spec with period `n` fires when `(current_iteration % n == 0)`
- [ ] Iteration numbering starts at 1 (first loop turn = iteration 1)
- [ ] Example: `.every-3.spec.md` fires on iterations 3, 6, 9, 12, …
- [ ] System specs fire **before** the regular spec phase within the same iteration
- [ ] Multiple system specs can fire in the same iteration (e.g., at iteration 6, both `.every-2.spec.md` and `.every-3.spec.md` fire)
- [ ] When multiple system specs are eligible in the same iteration, they fire sequentially in **alphabetical order** by full relative path. System specs have no priority tier because they have no state.
- [ ] System specs do NOT consume an iteration slot. The iteration counter advances exactly once per loop turn, after the regular phase.

### System Spec Output Contract

- [ ] System specs **MUST NOT** write to `state.json`
- [ ] System specs **MUST NOT** write to handoff
- [ ] System specs **MAY** write to guardrails. Guardrails are included in subsequent prompts (for both regular and system specs).
- [ ] System specs **MAY** write to any other project file. File changes are detected by the loop and count toward the downgrade rule (see below).
- [ ] The status file produced by a system spec (CONTINUE/ROTATE/DONE/STUCK) is ignored by the loop. The system-spec prompt template should not ask the agent to produce a status signal.

### Completion Check

- [ ] The completion check fires at the **start** of every loop turn, before the system phase.
- [ ] The check considers **only regular specs**: if all regular specs have `done_count >= 3`, Ralph exits 0.
- [ ] If no regular specs exist (only system specs), Ralph exits 0 immediately (system specs alone are not a valid configuration to drive a loop).
- [ ] System specs are never considered by the completion check. Their presence neither prevents nor causes exit.
- [ ] Because the check fires before the system phase, system specs do not run on the exit iteration.

### File-Change Downgrade

- [ ] When a system spec writes/modifies project files in its turn, the loop applies the existing downgrade rule: any regular spec currently at `done_count == 3` is downgraded to `done_count == 2`.
- [ ] This is the same rule that applies when a regular spec causes file changes — the source of the change does not matter, only that files changed.
- [ ] The downgrade applies **within the same iteration**: when the regular spec phase runs after the system phase, it sees the post-downgrade state.
- [ ] Guardrails changes by a system spec do not by themselves trigger the downgrade — the downgrade is driven by project file changes detected by the loop's existing modified-files snapshot.

### State File Format

- [ ] `state.json` contains entries **only for regular specs**. No entry is created or maintained for system specs.
- [ ] On startup, system specs are discovered from the filesystem and held in memory only. No persistence is needed because they have no per-spec state.
- [ ] If a system spec's filename changes (e.g., `cleanup.every-3.spec.md` renamed to `cleanup.every-5.spec.md`), the new period takes effect the next time discovery runs. Nothing to migrate in state.
- [ ] Renaming a regular spec into a system spec (`foo.spec.md` → `foo.every-3.spec.md`) removes its entry from state on next sync.
- [ ] Renaming a system spec into a regular spec (`foo.every-3.spec.md` → `foo.spec.md`) creates a fresh state entry (done_count=0, no last_status).

### Dedicated Prompt Template for System Specs

System specs use a prompt template distinct from regular IMPLEMENT and REVIEW templates. The template:

- [ ] Does NOT include `[IMPLEMENT]` or `[REVIEW]` mode markers
- [ ] Conveys that this is a periodic/system task running on a schedule (every n-th rotation)
- [ ] Includes the spec path, goal content (the system spec's own `.spec.md` body), and current guardrails
- [ ] Does NOT reference the 0→3 verification cycle (that concept is for regular specs only)
- [ ] Does NOT ask the agent to emit a status signal (CONTINUE/ROTATE/DONE/STUCK) — those are ignored
- [ ] Does NOT ask the agent to write a handoff
- [ ] Explicitly tells the agent that durable effects must go into project files or into guardrails

### Iteration Density Invariant

- [ ] Every loop turn runs the regular spec phase (one regular spec turn). The only way to skip the regular phase is to exit via the completion check at step 1.
- [ ] System specs that fire do not advance the iteration counter on their own — they share the iteration with the regular phase.
- [ ] There are no no-op iterations. If the loop is running, exactly one regular spec ran on that iteration, plus zero or more system specs.

### Concrete Iteration Traces

These traces are normative: implementations must produce exactly these spec selections.

#### Trace A — System spec fires alongside regular spec in the same iteration

Setup:
- `regular.spec.md` (regular), initial `done_count=0`, no `last_status`
- `cleanup.every-3.spec.md` (system)
- Regular agent: always returns DONE with no file changes
- System agent: always runs to completion with no file changes

| Iter | Exit check       | System phase    | Regular phase                        | End state         |
|------|------------------|-----------------|--------------------------------------|-------------------|
| 1    | regular 0/3, no  | 1%3≠0, skip     | regular (tier 0, new) → DONE         | regular 1/3       |
| 2    | regular 1/3, no  | 2%3≠0, skip     | regular (tier 4, dc=1) → DONE        | regular 2/3       |
| 3    | regular 2/3, no  | 3%3=0, cleanup  | regular (tier 4, dc=2) → DONE        | regular 3/3       |
| 4    | regular 3/3, **exit 0** | —          | —                                    | terminated        |

**Key invariant**: At iteration 3, both the system spec AND the regular spec run in the same iteration (two phases, one counter advance). At iteration 4, the exit check fires before the system phase, so cleanup does NOT get a final run even though 4 is the next loop turn.

#### Trace B — System spec writes a file, regular at 3/3 gets downgraded

Setup:
- `a.spec.md` (regular), initial state: `done_count=3`, `last_status=DONE`, `modified_files=False` (already verified from a prior session)
- `b.spec.md` (regular), initial state: `done_count=0`, no `last_status`
- `cleanup.every-2.spec.md` (system)
- a agent and b agent: always return DONE with no file changes
- cleanup agent script:
  - iter 2 → writes a file in the project
  - iter 4 → no file changes
  - iter 6 → no file changes

Tier reference (lower = higher priority):
- 0: new (no last_status); 1: modified (content hash changed); 2: non-DONE last_status; 3: DONE with file changes; 4: DONE no file changes (prefer lower dc within)

| Iter | Exit check       | System phase                                                        | Regular phase                                              | End state                              |
|------|------------------|---------------------------------------------------------------------|------------------------------------------------------------|----------------------------------------|
| 1    | a 3/3, b 0/3, no | 1%2≠0, skip                                                         | b (tier 0, new) beats a (tier 4) → DONE                    | a 3/3, b 1/3                           |
| 2    | a 3/3, b 1/3, no | 2%2=0, cleanup writes a file → **a downgraded 3/3 → 2/3**           | a (tier 4, dc=2), b (tier 4, dc=1) → b wins (lower dc) → DONE | a 2/3, b 2/3                       |
| 3    | a 2/3, b 2/3, no | 3%2≠0, skip                                                         | a (tier 4, dc=2), b (tier 4, dc=2) → a wins (alphabetical) → DONE | a 3/3, b 2/3                    |
| 4    | a 3/3, b 2/3, no | 4%2=0, cleanup runs, no file change                                 | a (tier 4, dc=3), b (tier 4, dc=2) → b wins (lower dc) → DONE | a 3/3, b 3/3                     |
| 5    | a 3/3, b 3/3, **exit 0** | —                                                           | —                                                          | terminated                             |

**Key invariant**: When cleanup writes a file in iteration 2, the downgrade applies immediately — within the same iteration — so the regular phase sees `a` at 2/3 rather than 3/3. The downgrade survives across iterations (a is still at 2/3 entering iter 3) and forces re-verification before the exit check at iter 5 fires.

### Edge Cases

- [ ] `.every-1.spec.md` is treated as a regular spec (not a system spec)
- [ ] `.every-0.spec.md` is treated as a regular spec
- [ ] `.every-abc.spec.md` is treated as a regular spec
- [ ] A project with only system specs (no regular specs) exits 0 immediately. System specs are auxiliary; they cannot drive a loop on their own.
- [ ] If a system spec's period changes (rename `.every-3` → `.every-5`), the new period takes effect on the next discovery pass — no state migration needed.
- [ ] System specs do not appear in the iteration counter or in completion percentages shown to the user (counters are about regular-spec progress).

### Constraints

- [ ] No new external dependencies are added
- [ ] Backwards compatibility: existing `*.spec.md` files (without `.every-[n]`) continue to work exactly as regular specs
- [ ] System specs are visually distinct in the UI (e.g., `[SYSTEM]` tag on console output) so users can tell them apart from regular specs in the iteration log
- [ ] The iteration counter shown to the user advances once per loop turn (since every loop turn has exactly one regular spec phase, this is unambiguous)

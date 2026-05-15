---
name: spec-writing
description: >
  Only use this skill when you need to add a new spec file or edit an existing
  spec for Ralph. It is NOT used during implementation, review, or bug fixing —
  only when writing or modifying specs that Ralph's agents will execute against.
---

# Ralph Spec Writing Skill

This skill teaches how to write effective spec files for Ralph — the autonomous
development supervisor. A spec is the single source of truth that tells an AI
agent **what** to build and **why**, without dictating **how**.

## When to Use This Skill

Use this skill when you (the human) need to:
- **Create a new spec** for a feature or capability Ralph doesn't yet have
- **Edit an existing spec** to extend scope, fix ambiguity, or add requirements

Do NOT use this skill during:
- Implementation rotations (agents read specs but don't write them)
- Review rotations (agents verify specs but don't write them)
- Bug fixing (fix the spec file directly if needed, then re-run)

## Core Principles

### 1. Check Existing Specs First

Before creating a new spec file, scan all existing `specs/*.spec.md` files to see
if an existing spec can semantically absorb the new requirement. If so, edit that
spec instead of duplicating effort.

Example: A requirement for "agent crash recovery" already lives in
`agent-cli-crash-handling.spec.md`. Don't create a separate `crash-recovery.spec.md`
— add to the existing one.

Only create a new spec when the feature is **truly distinct** — something that
couldn't reasonably be part of any existing spec without making it unwieldy.

### 2. Write for Humans First, Agents Second

A spec is a top-level requirement document. It must answer:
- **What** problem are we solving?
- **Why** does it matter? (user value, pain point)
- **Who** benefits from this?
- **How** will the user experience change?

Agents need this context to make good technical decisions. A spec that only says
"implement X" forces the agent to guess at priorities and trade-offs. A spec that
explains the user's problem lets the agent choose the right solution.

### 3. Minimal Technical Requirements

Specify **what** must happen, not **how** to do it. The agent is smart enough to
choose the best technical approach.

Only include technical requirements when they are genuinely mandatory — for
example, a platform constraint (must work on Linux + macOS + Windows), or a
dependency constraint (cannot add new external packages).

### 4. Verifiable Success Criteria

Every spec must have concrete, checkable success criteria. Each criterion should
be something an agent can independently verify without ambiguity. Use checkboxes
(`- [ ]`) so Ralph's verification cycle can track them.

Bad: "Make the code work on all platforms"
Good: "Platform detection is automatic — no user configuration needed"

## Spec Anatomy

Every spec follows this structure (sections are ordered by importance):

```markdown
# Spec Title

One-line summary of what this spec covers. A human can read this and know the
scope without diving deeper.

## Problem

(Optional but recommended) What problem does this solve? Why does it matter?
Be specific — describe the pain point, not just the symptom. Numbered lists
work well here.

## Goal

What Ralph should achieve. Keep it to one or two sentences. This is the north
star — everything else supports it.

## Success Criteria

Concrete, verifiable conditions that prove the spec is complete. Group related
criteria under sub-headings. Each criterion must be independently checkable.
Use checkboxes (`- [ ]`).

### Sub-category (e.g., "Core Behavior", "Edge Cases", "Testing")

- [ ] Criterion 1
- [ ] Criterion 2

## Constraints

(Optional) What the agent MUST NOT do, or must always do. Be explicit about:
- Backwards compatibility requirements
- Dependency constraints
- Scope boundaries (what's out of scope)

## Implementation Notes

(Optional) Hints for the agent — things you know that might help, but aren't
mandatory. This is different from constraints; it's "here's something to
consider" rather than "you must do this."
```

### Section Guidance

| Section | When to Include | Length |
|---------|----------------|--------|
| Title | Always | One line |
| Summary | Always | 1-2 sentences |
| Problem | When the "why" isn't obvious | Short, numbered list |
| Goal | Always | 1-2 sentences |
| Success Criteria | Always | As many as needed |
| Constraints | When there are real limits | Concise |
| Implementation Notes | When you have useful context | Brief |

## Writing Effective Success Criteria

### Good Criteria

Good criteria are **specific**, **verifiable**, and **unambiguous**:

```markdown
### Auto-cleanup

- [ ] Sleep prevention stops when Ralph exits normally (exit 0)
- [ ] Sleep prevention stops on Ctrl+C (SIGINT)
- [ ] If sleep prevention fails, Ralph continues with a warning — does NOT exit with error
```

Each criterion describes a concrete condition that can be checked.

### Bad Criteria

Avoid vague, subjective, or implementation-dependent criteria:

```markdown
<!-- BAD: vague -->
- [ ] The feature should work well

<!-- BAD: implementation detail -->
- [ ] Use subprocess.Popen to start caffeinate

<!-- BAD: too broad -->
- [ ] Handle all edge cases properly
```

### Criterion Writing Patterns

**Behavioral** — describe what happens:
```markdown
- [ ] Non-zero exit codes from agent CLI are detected as crashes
```

**Negative** — describe what must NOT happen:
```markdown
- [ ] Agents that exit successfully with zero exit code are not flagged as crashed
```

**Conditional** — describe behavior under specific conditions:
```markdown
- [ ] If the platform mechanism is unavailable, log a warning but continue running
```

**Testing** — when a criterion requires specific test coverage:
```markdown
- [ ] Tests verify that cleanup happens on all exit paths
- [ ] MUST TEST: Running `ralph run --agents pi --max 10` saves configuration
```

## Spec File Naming

Name files as `[name].spec.md` in the `specs/` directory. Names should be:
- **Descriptive** — someone scanning the directory should understand the scope
- **Noun phrases** — not verbs ("crash handling" not "handle crashes")
- **Specific** — avoid overly broad names

Good names:
- `agent-cli-crash-handling.spec.md`
- `no-sleep-mode.spec.md`
- `verification-counter-behavior.spec.md`

Bad names:
- `fix-bug.spec.md` (too vague)
- `improve-everything.spec.md` (too broad)
- `handle-crash.spec.md` (verb-based, should be noun-phrase)

## Common Spec Patterns

### Feature Implementation Spec

For adding a new capability to Ralph:

```markdown
# Feature Name

When [context], Ralph should [behavior].

## Problem

1. Current situation causes pain point
2. Users can't do X
3. This limits Ralph's usefulness for Y

## Goal

[One sentence summary]

## Success Criteria

### Core Behavior
- [ ] Criterion...

### Edge Cases
- [ ] Criterion...

### Testing
- [ ] Criterion...
```

### Refactoring Spec

When the goal is to improve code quality without changing behavior, add an explicit
refactoring allowance section:

```markdown
## Refactoring Allowance

- This spec explicitly allows refactoring to improve code quality
- Breaking changes to internal APIs are allowed
- Public CLI interface must remain unchanged
- Tests may be updated or rewritten to match refactored code
```

### Cross-Cutting Spec

For features that touch multiple parts of the codebase (like no-sleep-mode which
touches loop.py, agent.py, and platform detection), include a platform support
table:

```markdown
### Platform Support

| Platform | Mechanism | Notes |
|----------|-----------|-------|
| Linux | systemd-inhibit | Primary mechanism |
| macOS | caffeinate -dims | Native power management |
| Windows | SetThreadExecutionState | Native Win32 API |
```

### Interface/Command Spec

For specs that define CLI behavior (like `ralph-commands.spec.md`), document each
command with: purpose, syntax, behavior, error cases. This is more detailed than
typical specs because the spec IS the contract.

## Review Checklist

Before committing a spec, ask:

1. **Is this truly a new feature?** → If not, edit existing spec instead
2. **Would a stranger understand the "why" from this spec?** → If not, add Problem section
3. **Are all success criteria independently verifiable?** → No vague language
4. **Did I avoid dictating implementation details?** → Agent should decide how
5. **Is the scope bounded?** → Clear what's in and what's out
6. **Would an agent making its first rotation be able to execute this correctly?**
7. **Are there enough constraints to prevent wrong approaches?** (but not so many that the agent can't innovate)

## Examples from Ralph's Own Spec Suite

### Good: `no-sleep-mode.spec.md`

This spec excels at:
- Clear problem statement with numbered pain points
- Solution description with platform-by-platform breakdown
- Exhaustive success criteria organized by concern (behavior, cleanup, edge cases)
- Explicit design decisions documented in the Problem/Solution section
- Constraints baked into criteria ("does NOT fail the entire run")

### Good: `agent-cli-crash-handling.spec.md`

This spec shows how to:
- Keep it relatively short while being precise
- Distinguish related concepts (crash vs exhaustion) with clear definitions
- Group criteria by concern (detection, recovery, context preservation)

### Good: `multi-spec-mode.spec.md`

This spec demonstrates:
- Using tables for resource scoping
- Providing example execution sequences
- Comprehensive coverage of edge cases and restart scenarios
- Clear priority ordering rules

## Tips

- **Start with the Problem section** — if you can't articulate "why," the spec
  probably isn't needed (or an existing spec should cover it)
- **Write criteria first, prose second** — once you know what "done" looks like,
  the surrounding explanation becomes easier to write
- **Think about the agent reading this at 3 AM** — would they make the right
  decisions with only this document and no prior context?
- **Iterate on specs too** — a spec that turns out to be unclear during
  implementation should be updated, not worked around

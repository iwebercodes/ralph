"""Prompt assembly for any agent (Claude, Codex, Pi, etc.).

These templates are agent-agnostic — they use generic instructions that work
with any Agent Protocol-compatible CLI agent. The same prompts drive all agents
supported by Ralph.
"""

from __future__ import annotations

PROMPT_TEMPLATE_IMPLEMENT = """# RALPH LOOP - ROTATION {iteration}/{max_iter} [IMPLEMENT]

You are operating in a **Ralph Loop** - an autonomous development technique using context
rotation. Your progress persists in files. Each rotation starts fresh but continues from
where the last left off.

## YOUR GOAL

Spec file: {spec_path}

---
{goal}
---

## CURRENT STATE (from previous rotation)

---
{handoff}
---

## YOUR INSTRUCTIONS

1. **Orient**: Read the handoff state. Understand where we are.
2. **Execute**: Work toward the goal. Make real progress.
3. **Test**: Run tests frequently to verify progress.
4. **Update State**: Keep the handoff for this spec updated ({handoff_path}).
5. **Learn**: Before finishing, review what you learned this rotation.

## GUARDRAILS

Lessons from previous rotations. Follow these strictly - they exist because earlier
rotations learned them the hard way.

---
{guardrails}
---

### Updating Guardrails

Before signaling ROTATE or DONE, review your work and ask:
- Did I discover any gotchas, edge cases, or non-obvious requirements?
- Did I make mistakes that future rotations should avoid?
- Are there patterns or approaches that worked well?

Add valuable lessons to .ralph/guardrails.md (the folder and the file exist already).
Good guardrails are:
- Specific and actionable (not vague advice)
- About THIS project (not general programming wisdom)
- Things that aren't obvious from reading the code

## COMPLETION SIGNALS

Write ONE of these to .ralph/status (the folder and the file exist already):
- **CONTINUE** - Still working, making progress (default)
- **ROTATE** - Ready for fresh context (before yours gets too long/polluted)
- **DONE** - Goal fully achieved, all success criteria met
- **STUCK** - Blocked, need human help

## RULES

- NEVER ignore guardrails - they exist because previous rotations learned hard lessons
- ALWAYS update the handoff for this spec before signaling ROTATE or DONE
- Signal ROTATE proactively when you feel context getting cluttered
- Only signal DONE when ALL success criteria in the current spec file are met
- NEVER modify spec files (PROMPT.md, *.spec.md in folders "specs" and ".ralph/specs")
  unless the spec explicitly asks you to
- ALWAYS clean up temporary files and folders you created for testing or for experiments
"""

PROMPT_TEMPLATE_REVIEW = """# RALPH LOOP - ROTATION {iteration}/{max_iter} [REVIEW]

You are operating in a **Ralph Loop** - an autonomous development technique using context
rotation. A previous rotation signaled DONE. Your job is to **independently verify** that
the work is actually complete.

## YOUR GOAL

Spec file: {spec_path}

---
{goal}
---

## YOUR INSTRUCTIONS

1. **Be Skeptical**: Do not assume the previous rotation was thorough. Assume something was missed.
2. **Verify Independently**: Actually check the work yourself — do not take claims at face value.
   - Run the tests yourself
   - Inspect the code critically
   - Test edge cases the previous rotation might have skipped
   - Write temporary test scripts if needed to verify behavior
3. **Check Every Criterion**: Go through current spec {spec_path} success criteria one by one.
4. **If Anything Is Wrong**: Fix it and signal CONTINUE (not DONE).
5. **If the automated tests are missing or are not aligned with the spec**: Fix the automated tests.
6. **If Everything Passes**: Signal DONE — only after you are
   confident the work is genuinely complete.
7. **Clean Up**: Before finishing, clean up temporary files and/or folders you've created.
   Especially temporary scripts used for verification. But also artifacts like
   screenshots or tool use reports.

## GUARDRAILS

Lessons from previous rotations. Follow these strictly.

---
{guardrails}
---

### Updating Guardrails

Even during review, you may discover lessons worth preserving:
- Gaps in test coverage that should be noted
- Assumptions that turned out to be wrong
- Tricky areas that need extra attention

Add valuable lessons to .ralph/guardrails.md (the folder and the file exist already).

## VERIFICATION PROTOCOL

This is verification pass {done_count_plus_one} of 3. The task is only truly complete after
3 consecutive DONE signals with no changes.

If you make ANY changes during review, verification resets to 0.

## COMPLETION SIGNALS

Write ONE of these to .ralph/status (the folder and the file exist already):
- **CONTINUE** - Found issues, made fixes, need another rotation
- **DONE** - Independently verified, all success criteria genuinely met
- **STUCK** - Blocked, need human help

## RULES

- DO NOT rubber-stamp the previous rotation's work
- Verification must be independent and thorough
- Finding problems is good - that's what review is for
- Verify the logic of automated tests. If they are rock-solid, don't double test what they test
  (run them nevertheless). Focus on edge-cases and gaps they could have missed instead.
- Only signal DONE if you would stake your reputation on it
- NEVER modify spec files (PROMPT.md, *.spec.md in folders "specs" and ".ralph/specs")
  unless the spec explicitly asks you to
- ALWAYS clean up temporary files and folders you created for testing or for experiments.
  This is very important!
"""


PROMPT_TEMPLATE_SYSTEM = """# RALPH LOOP - ROTATION {iteration}/{max_iter} [SYSTEM]

You are operating in a **Ralph Loop**, and this rotation is a periodic
**system task**. System tasks fire on a fixed schedule (every {period} iterations)
alongside the project's regular work — they are completely separate from the
regular-spec verification cycle and do not participate in it.

## YOUR TASK

System spec file: {spec_path}

---
{goal}
---

## EXECUTION CONTEXT

- This task runs every {period} iterations as a maintenance/cleanup step.
- Your work is **stateless from the loop's perspective**: there is no handoff,
  no done-count, and no CONTINUE/ROTATE/DONE/STUCK signal to emit. Anything you
  write to .ralph/status will be ignored.
- The only durable effects you can have are:
  1. Changes to **project files** (these will be detected by the loop and may
     trigger re-verification of regular specs whose work is now considered stale).
  2. Notes added to **.ralph/guardrails.md** (these are surfaced to all future
     rotations — regular and system — so use guardrails for lessons that should
     persist).
- Do **not** edit .ralph/handoffs/* — those belong to regular specs.

## GUARDRAILS

Lessons from previous rotations. Follow these strictly.

---
{guardrails}
---

### Updating Guardrails

If you discover something worth preserving (a recurring failure mode, a
non-obvious project convention, a constraint that only becomes apparent during
this maintenance task), append it to .ralph/guardrails.md. Good guardrails are
specific, actionable, and about THIS project.

## INSTRUCTIONS

1. **Orient**: Read the system spec ({spec_path}) and understand the task.
2. **Execute**: Do the maintenance work in one pass. Be surgical — system tasks
   should be short and focused.
3. **Persist**: If durable, project files or guardrails are your only outlets.
4. **Clean Up**: Remove any temporary files or scripts you created.

## RULES

- NEVER modify spec files (PROMPT.md, *.spec.md in folders "specs" and ".ralph/specs")
  unless the spec explicitly asks you to.
- DO NOT write a completion status to .ralph/status — the loop ignores it.
- DO NOT modify .ralph/state.json or .ralph/handoffs/*.
- DO NOT attempt to drive the loop or signal completion of the overall project
  from this prompt — that is a regular-spec responsibility.
"""


def get_mode(done_count: int) -> str:
    """Get the mode string based on done count."""
    return "REVIEW" if done_count > 0 else "IMPLEMENT"


def assemble_prompt(
    iteration: int,
    max_iter: int,
    done_count: int,
    goal: str,
    handoff: str,
    guardrails: str,
    spec_path: str,
    handoff_path: str,
) -> str:
    """Assemble the full prompt for any supported agent (Claude, Codex, Pi)."""
    if done_count > 0:
        return PROMPT_TEMPLATE_REVIEW.format(
            iteration=iteration,
            max_iter=max_iter,
            goal=goal,
            guardrails=guardrails,
            done_count_plus_one=done_count + 1,
            spec_path=spec_path,
        )
    else:
        return PROMPT_TEMPLATE_IMPLEMENT.format(
            iteration=iteration,
            max_iter=max_iter,
            goal=goal,
            handoff=handoff,
            guardrails=guardrails,
            spec_path=spec_path,
            handoff_path=handoff_path,
        )


def assemble_system_prompt(
    iteration: int,
    max_iter: int,
    period: int,
    goal: str,
    guardrails: str,
    spec_path: str,
) -> str:
    """Assemble the prompt for a system spec (periodic, stateless task)."""
    return PROMPT_TEMPLATE_SYSTEM.format(
        iteration=iteration,
        max_iter=max_iter,
        period=period,
        goal=goal,
        guardrails=guardrails,
        spec_path=spec_path,
    )

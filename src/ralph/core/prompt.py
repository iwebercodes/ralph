"""Prompt assembly for Claude invocations."""

from __future__ import annotations

PROMPT_TEMPLATE_IMPLEMENT = """# RALPH LOOP - ROTATION {iteration}/{max_iter} [IMPLEMENT]

You are operating in a **Ralph Loop** - an autonomous development technique using context
rotation. Your progress persists in files. Each rotation starts fresh but continues from
where the last left off.

## YOUR GOAL

{goal}

## CURRENT STATE (from previous rotation)

{handoff}

## YOUR INSTRUCTIONS

1. **Orient**: Read the handoff state. Understand where we are.
2. **Execute**: Work toward the goal. Make real progress.
3. **Test**: Run tests frequently to verify progress.
4. **Update State**: Keep .ralph/handoff.md current with your progress.
5. **Learn**: Before finishing, review what you learned this rotation.

## GUARDRAILS

Lessons from previous rotations. Follow these strictly - they exist because earlier
rotations learned them the hard way.

{guardrails}

### Updating Guardrails

Before signaling ROTATE or DONE, review your work and ask:
- Did I discover any gotchas, edge cases, or non-obvious requirements?
- Did I make mistakes that future rotations should avoid?
- Are there patterns or approaches that worked well?

Add valuable lessons to .ralph/guardrails.md. Good guardrails are:
- Specific and actionable (not vague advice)
- About THIS project (not general programming wisdom)
- Things that aren't obvious from reading the code

## COMPLETION SIGNALS

Write ONE of these to .ralph/status:
- **CONTINUE** - Still working, making progress (default)
- **ROTATE** - Ready for fresh context (before yours gets too long/polluted)
- **DONE** - Goal fully achieved, all success criteria met
- **STUCK** - Blocked, need human help

## RULES

- NEVER ignore guardrails - they exist because previous rotations learned hard lessons
- ALWAYS update handoff.md before signaling ROTATE or DONE
- Signal ROTATE proactively when you feel context getting cluttered
- Only signal DONE when ALL success criteria in PROMPT.md are met
"""

PROMPT_TEMPLATE_REVIEW = """# RALPH LOOP - ROTATION {iteration}/{max_iter} [REVIEW]

You are operating in a **Ralph Loop** - an autonomous development technique using context
rotation. A previous rotation signaled DONE. Your job is to **independently verify** that
the work is actually complete.

## YOUR GOAL

{goal}

## CLAIMED STATE (from previous rotation - DO NOT TRUST BLINDLY)

{handoff}

## YOUR INSTRUCTIONS

1. **Be Skeptical**: The previous rotation may have missed something. Assume it did.
2. **Verify Independently**: Don't just read the handoff - actually check the work.
   - Run the tests yourself
   - Inspect the code critically
   - Test edge cases the previous rotation might have skipped
   - Write temporary test scripts if needed to verify behavior
3. **Check Every Criterion**: Go through PROMPT.md success criteria one by one.
4. **If Anything Is Wrong**: Fix it, update handoff.md, and signal CONTINUE (not DONE).
5. **If Everything Passes**: Update handoff.md confirming your verification, signal DONE.

## GUARDRAILS

Lessons from previous rotations. Follow these strictly.

{guardrails}

### Updating Guardrails

Even during review, you may discover lessons worth preserving:
- Gaps in test coverage that should be noted
- Assumptions that turned out to be wrong
- Tricky areas that need extra attention

Add valuable lessons to .ralph/guardrails.md.

## VERIFICATION PROTOCOL

This is verification pass {done_count_plus_one} of 3. The task is only truly complete after
3 consecutive DONE signals with no changes.

If you make ANY changes during review, verification resets to 0.

## COMPLETION SIGNALS

Write ONE of these to .ralph/status:
- **CONTINUE** - Found issues, made fixes, need another rotation
- **DONE** - Independently verified, all success criteria genuinely met
- **STUCK** - Blocked, need human help

## RULES

- DO NOT rubber-stamp the previous rotation's work
- Verification must be independent and thorough
- Finding problems is good - that's what review is for
- Only signal DONE if you would stake your reputation on it
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
) -> str:
    """Assemble the full prompt for Claude."""
    if done_count > 0:
        return PROMPT_TEMPLATE_REVIEW.format(
            iteration=iteration,
            max_iter=max_iter,
            goal=goal,
            handoff=handoff,
            guardrails=guardrails,
            done_count_plus_one=done_count + 1,
        )
    else:
        return PROMPT_TEMPLATE_IMPLEMENT.format(
            iteration=iteration,
            max_iter=max_iter,
            goal=goal,
            handoff=handoff,
            guardrails=guardrails,
        )

"""Prompt assembly for Claude invocations."""

from __future__ import annotations

PROMPT_TEMPLATE = """# RALPH LOOP - ROTATION {iteration}/{max_iter} [{mode}]

You are operating in a **Ralph Loop** - an autonomous development technique using context
rotation. Your progress persists in files. Each rotation starts fresh but continues from
where the last left off.

## YOUR GOAL

{goal}

## GUARDRAILS (lessons from previous rotations - MUST follow these)

{guardrails}

## CURRENT STATE (from previous rotation)

{handoff}

## YOUR INSTRUCTIONS

1. **Orient**: Read the handoff state. Understand where we are.
2. **Execute**: Work toward the goal. Make real progress.
3. **Test**: Run tests frequently to verify progress.
4. **Update State**: Keep .ralph/handoff.md current with your progress.
5. **Learn**: If you discover something important, add it to .ralph/guardrails.md

## COMPLETION SIGNALS

Write ONE of these to .ralph/status:
- **CONTINUE** - Still working, making progress (default)
- **ROTATE** - Ready for fresh context (before yours gets too long/polluted)
- **DONE** - Goal fully achieved, all success criteria met
- **STUCK** - Blocked, need human help

## COMPLETION PROTOCOL

Signaling DONE triggers a verification cycle:
- You must confirm completion 3 times total
- Each review rotation checks your work thoroughly
- If you make changes during review, verification resets
- Only after 3 consecutive DONE signals (with no changes) is the task truly complete

## RULES

- NEVER ignore guardrails - they exist because previous rotations learned hard lessons
- ALWAYS update handoff.md before signaling ROTATE or DONE
- Keep handoff.md detailed but concise - it's your memory across rotations
- Signal ROTATE proactively when you feel context getting cluttered
- Only signal DONE when ALL success criteria in PROMPT.md are met
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
    mode = get_mode(done_count)

    return PROMPT_TEMPLATE.format(
        iteration=iteration,
        max_iter=max_iter,
        mode=mode,
        goal=goal,
        handoff=handoff,
        guardrails=guardrails,
    )

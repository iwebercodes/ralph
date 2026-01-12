"""Tests for prompt assembly."""

from __future__ import annotations

from ralph.core.prompt import assemble_prompt, get_mode


def test_get_mode_implement() -> None:
    """Test mode is IMPLEMENT when done_count is 0."""
    assert get_mode(0) == "IMPLEMENT"


def test_get_mode_review() -> None:
    """Test mode is REVIEW when done_count > 0."""
    assert get_mode(1) == "REVIEW"
    assert get_mode(2) == "REVIEW"
    assert get_mode(3) == "REVIEW"


def test_assemble_prompt_basic() -> None:
    """Test basic prompt assembly."""
    prompt = assemble_prompt(
        iteration=1,
        max_iter=20,
        done_count=0,
        goal="Build a thing",
        handoff="Current state",
        guardrails="Don't break stuff",
    )

    assert "ROTATION 1/20" in prompt
    assert "[IMPLEMENT]" in prompt
    assert "Build a thing" in prompt
    assert "Current state" in prompt
    assert "Don't break stuff" in prompt


def test_assemble_prompt_review_mode() -> None:
    """Test prompt assembly in review mode."""
    prompt = assemble_prompt(
        iteration=5,
        max_iter=10,
        done_count=2,
        goal="Goal",
        handoff="Handoff",
        guardrails="Guardrails",
    )

    assert "ROTATION 5/10" in prompt
    assert "[REVIEW]" in prompt


def test_assemble_prompt_contains_instructions() -> None:
    """Test prompt contains all required sections."""
    prompt = assemble_prompt(
        iteration=1,
        max_iter=20,
        done_count=0,
        goal="Goal",
        handoff="Handoff",
        guardrails="Guardrails",
    )

    # Check required sections
    assert "YOUR GOAL" in prompt
    assert "GUARDRAILS" in prompt
    assert "CURRENT STATE" in prompt
    assert "YOUR INSTRUCTIONS" in prompt
    assert "COMPLETION SIGNALS" in prompt
    assert "COMPLETION PROTOCOL" in prompt
    assert "RULES" in prompt


def test_assemble_prompt_contains_signals() -> None:
    """Test prompt contains all status signals."""
    prompt = assemble_prompt(
        iteration=1,
        max_iter=20,
        done_count=0,
        goal="Goal",
        handoff="Handoff",
        guardrails="Guardrails",
    )

    assert "CONTINUE" in prompt
    assert "ROTATE" in prompt
    assert "DONE" in prompt
    assert "STUCK" in prompt

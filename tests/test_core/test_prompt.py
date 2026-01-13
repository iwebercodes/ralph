"""Tests for prompt assembly."""

from __future__ import annotations

from pathlib import Path

from ralph.core.prompt import assemble_prompt, get_mode
from ralph.core.state import read_guardrails, read_handoff, read_prompt_md


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
    """Test IMPLEMENT prompt contains all required sections."""
    prompt = assemble_prompt(
        iteration=1,
        max_iter=20,
        done_count=0,
        goal="Goal",
        handoff="Handoff",
        guardrails="Guardrails",
    )

    # Check required sections for IMPLEMENT mode
    assert "YOUR GOAL" in prompt
    assert "GUARDRAILS" in prompt
    assert "CURRENT STATE" in prompt
    assert "YOUR INSTRUCTIONS" in prompt
    assert "COMPLETION SIGNALS" in prompt
    assert "Updating Guardrails" in prompt
    assert "RULES" in prompt


def test_assemble_prompt_review_contains_verification() -> None:
    """Test REVIEW prompt contains verification-specific sections."""
    prompt = assemble_prompt(
        iteration=5,
        max_iter=20,
        done_count=1,
        goal="Goal",
        handoff="Handoff",
        guardrails="Guardrails",
    )

    # Check required sections for REVIEW mode
    assert "[REVIEW]" in prompt
    assert "CLAIMED STATE" in prompt
    assert "DO NOT TRUST BLINDLY" in prompt
    assert "Be Skeptical" in prompt
    assert "Verify Independently" in prompt
    assert "VERIFICATION PROTOCOL" in prompt
    assert "verification pass 2 of 3" in prompt
    assert "rubber-stamp" in prompt


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


# =============================================================================
# Integration Tests - Full File Read -> Prompt Assembly Pipeline
# =============================================================================


def test_integration_full_prompt_assembly(initialized_project: Path) -> None:
    """Test full pipeline: create files, read through actual code path, verify in assembled prompt.

    This is the key integration test that verifies all three file contents
    (PROMPT.md, handoff.md, guardrails.md) appear correctly in the final prompt.
    """
    # Create files with unique identifiable content
    goal_content = (
        "# UNIQUE_GOAL_MARKER_12345\n\nBuild the feature\n\n# Success Criteria\n\n- [ ] Test passes"
    )
    handoff_content = "# UNIQUE_HANDOFF_MARKER_67890\n\n## Completed\n\nPrevious work done"
    guardrails_content = "# UNIQUE_GUARDRAILS_MARKER_ABCDE\n\n- Never break production"

    # Write files through the actual filesystem
    (initialized_project / "PROMPT.md").write_text(goal_content)
    (initialized_project / ".ralph" / "handoff.md").write_text(handoff_content)
    (initialized_project / ".ralph" / "guardrails.md").write_text(guardrails_content)

    # Read through the actual code paths
    goal = read_prompt_md(initialized_project)
    handoff = read_handoff(initialized_project)
    guardrails = read_guardrails(initialized_project)

    assert goal is not None

    # Assemble the prompt
    prompt = assemble_prompt(
        iteration=1,
        max_iter=20,
        done_count=0,
        goal=goal,
        handoff=handoff,
        guardrails=guardrails,
    )

    # Verify ALL THREE file contents appear in the final prompt
    assert "UNIQUE_GOAL_MARKER_12345" in prompt, "Goal content missing from assembled prompt"
    assert "UNIQUE_HANDOFF_MARKER_67890" in prompt, "Handoff content missing from assembled prompt"
    assert "UNIQUE_GUARDRAILS_MARKER_ABCDE" in prompt, (
        "Guardrails content missing from assembled prompt"
    )

    # Also verify actual content is there
    assert "Build the feature" in prompt
    assert "Previous work done" in prompt
    assert "Never break production" in prompt


def test_integration_with_windows_line_endings(initialized_project: Path) -> None:
    """Test full pipeline with Windows line endings in all files."""
    goal_content = "# Goal\r\n\r\nWINDOWS_GOAL_CONTENT\r\n\r\n# Success Criteria\r\n\r\n- [ ] Done"
    handoff_content = "# Handoff\r\n\r\nWINDOWS_HANDOFF_CONTENT"
    guardrails_content = "# Guardrails\r\n\r\nWINDOWS_GUARDRAILS_CONTENT"

    (initialized_project / "PROMPT.md").write_bytes(goal_content.encode("utf-8"))
    (initialized_project / ".ralph" / "handoff.md").write_bytes(handoff_content.encode("utf-8"))
    (initialized_project / ".ralph" / "guardrails.md").write_bytes(
        guardrails_content.encode("utf-8")
    )

    goal = read_prompt_md(initialized_project)
    handoff = read_handoff(initialized_project)
    guardrails = read_guardrails(initialized_project)

    assert goal is not None

    prompt = assemble_prompt(
        iteration=1,
        max_iter=20,
        done_count=0,
        goal=goal,
        handoff=handoff,
        guardrails=guardrails,
    )

    assert "WINDOWS_GOAL_CONTENT" in prompt
    assert "WINDOWS_HANDOFF_CONTENT" in prompt
    assert "WINDOWS_GUARDRAILS_CONTENT" in prompt


def test_integration_with_utf8_bom(initialized_project: Path) -> None:
    """Test full pipeline with UTF-8 BOM in all files."""
    bom = b"\xef\xbb\xbf"
    goal_content = "# Goal\n\nBOM_GOAL_CONTENT\n\n# Success\n\n- [ ] Done"
    handoff_content = "# Handoff\n\nBOM_HANDOFF_CONTENT"
    guardrails_content = "# Guardrails\n\nBOM_GUARDRAILS_CONTENT"

    (initialized_project / "PROMPT.md").write_bytes(bom + goal_content.encode("utf-8"))
    (initialized_project / ".ralph" / "handoff.md").write_bytes(
        bom + handoff_content.encode("utf-8")
    )
    (initialized_project / ".ralph" / "guardrails.md").write_bytes(
        bom + guardrails_content.encode("utf-8")
    )

    goal = read_prompt_md(initialized_project)
    handoff = read_handoff(initialized_project)
    guardrails = read_guardrails(initialized_project)

    assert goal is not None

    prompt = assemble_prompt(
        iteration=1,
        max_iter=20,
        done_count=0,
        goal=goal,
        handoff=handoff,
        guardrails=guardrails,
    )

    assert "BOM_GOAL_CONTENT" in prompt
    assert "BOM_HANDOFF_CONTENT" in prompt
    assert "BOM_GUARDRAILS_CONTENT" in prompt


def test_integration_with_unicode_content(initialized_project: Path) -> None:
    """Test full pipeline with Unicode content (emojis, non-ASCII)."""
    goal_content = "# Goal 🎯\n\nBuild feature with émojis\n\n# Success 日本語\n\n- [ ] 完了"
    handoff_content = "# Handoff 📋\n\n## Complété ✅\n\nTäsk with ümläuts"
    guardrails_content = "# Guardrails 🛡️\n\n- Règle numéro un: 不要破坏"

    (initialized_project / "PROMPT.md").write_text(goal_content, encoding="utf-8")
    (initialized_project / ".ralph" / "handoff.md").write_text(handoff_content, encoding="utf-8")
    (initialized_project / ".ralph" / "guardrails.md").write_text(
        guardrails_content, encoding="utf-8"
    )

    goal = read_prompt_md(initialized_project)
    handoff = read_handoff(initialized_project)
    guardrails = read_guardrails(initialized_project)

    assert goal is not None

    prompt = assemble_prompt(
        iteration=1,
        max_iter=20,
        done_count=0,
        goal=goal,
        handoff=handoff,
        guardrails=guardrails,
    )

    assert "🎯" in prompt
    assert "émojis" in prompt
    assert "日本語" in prompt
    assert "📋" in prompt
    assert "ümläuts" in prompt
    assert "🛡️" in prompt
    assert "不要破坏" in prompt


def test_integration_with_special_formatting_chars(initialized_project: Path) -> None:
    """Test full pipeline with characters that could break string formatting."""
    goal_content = (
        "# Goal\n\nUse {placeholder} and 50% and C:\\path\\file\n\n# Success\n\n- [ ] Done"
    )
    handoff_content = '# Handoff\n\nJSON: {"key": "value"}\nPercent: %s %d %%'
    guardrails_content = "# Guardrails\n\n- Path: C:\\Users\\test\n- Template: {{nested}}"

    (initialized_project / "PROMPT.md").write_text(goal_content)
    (initialized_project / ".ralph" / "handoff.md").write_text(handoff_content)
    (initialized_project / ".ralph" / "guardrails.md").write_text(guardrails_content)

    goal = read_prompt_md(initialized_project)
    handoff = read_handoff(initialized_project)
    guardrails = read_guardrails(initialized_project)

    assert goal is not None

    prompt = assemble_prompt(
        iteration=1,
        max_iter=20,
        done_count=0,
        goal=goal,
        handoff=handoff,
        guardrails=guardrails,
    )

    # All special characters should appear correctly
    assert "{placeholder}" in prompt
    assert "50%" in prompt
    assert "C:\\path\\file" in prompt
    assert '{"key": "value"}' in prompt
    assert "%s %d %%" in prompt
    assert "C:\\Users\\test" in prompt
    assert "{{nested}}" in prompt


def test_integration_with_large_files(initialized_project: Path) -> None:
    """Test full pipeline with large file content (>50KB)."""
    # Create large content
    large_goal = "# Goal\n\n" + "G" * 20000 + "\n\n# Success\n\n- [ ] Done"
    large_handoff = "# Handoff\n\n" + "H" * 20000
    large_guardrails = "# Guardrails\n\n" + "R" * 20000

    assert len(large_goal) > 20000
    assert len(large_handoff) > 20000
    assert len(large_guardrails) > 20000

    (initialized_project / "PROMPT.md").write_text(large_goal)
    (initialized_project / ".ralph" / "handoff.md").write_text(large_handoff)
    (initialized_project / ".ralph" / "guardrails.md").write_text(large_guardrails)

    goal = read_prompt_md(initialized_project)
    handoff = read_handoff(initialized_project)
    guardrails = read_guardrails(initialized_project)

    assert goal is not None

    prompt = assemble_prompt(
        iteration=1,
        max_iter=20,
        done_count=0,
        goal=goal,
        handoff=handoff,
        guardrails=guardrails,
    )

    # All content should be present
    assert "G" * 100 in prompt
    assert "H" * 100 in prompt
    assert "R" * 100 in prompt
    # And prompt should be larger than combined input
    assert len(prompt) > 60000


def test_integration_missing_handoff_uses_default(initialized_project: Path) -> None:
    """Test that missing handoff.md uses default template."""
    from ralph.core.state import HANDOFF_TEMPLATE

    goal_content = "# Goal\n\nTest\n\n# Success\n\n- [ ] Done"
    guardrails_content = "# Guardrails\n\nRules"

    (initialized_project / "PROMPT.md").write_text(goal_content)
    (initialized_project / ".ralph" / "guardrails.md").write_text(guardrails_content)
    (initialized_project / ".ralph" / "handoff.md").unlink()

    goal = read_prompt_md(initialized_project)
    handoff = read_handoff(initialized_project)
    guardrails = read_guardrails(initialized_project)

    assert goal is not None
    assert handoff == HANDOFF_TEMPLATE

    prompt = assemble_prompt(
        iteration=1,
        max_iter=20,
        done_count=0,
        goal=goal,
        handoff=handoff,
        guardrails=guardrails,
    )

    # Default template content should be in prompt
    assert "## Completed" in prompt
    assert "## In Progress" in prompt


def test_integration_missing_guardrails_uses_default(initialized_project: Path) -> None:
    """Test that missing guardrails.md uses default template."""
    from ralph.core.state import GUARDRAILS_TEMPLATE

    goal_content = "# Goal\n\nTest\n\n# Success\n\n- [ ] Done"
    handoff_content = "# Handoff\n\nState"

    (initialized_project / "PROMPT.md").write_text(goal_content)
    (initialized_project / ".ralph" / "handoff.md").write_text(handoff_content)
    (initialized_project / ".ralph" / "guardrails.md").unlink()

    goal = read_prompt_md(initialized_project)
    handoff = read_handoff(initialized_project)
    guardrails = read_guardrails(initialized_project)

    assert goal is not None
    assert guardrails == GUARDRAILS_TEMPLATE

    prompt = assemble_prompt(
        iteration=1,
        max_iter=20,
        done_count=0,
        goal=goal,
        handoff=handoff,
        guardrails=guardrails,
    )

    assert "# Guardrails" in prompt


def test_integration_empty_handoff_file(initialized_project: Path) -> None:
    """Test prompt assembly when handoff.md is empty."""
    goal_content = "# Goal\n\nTest\n\n# Success\n\n- [ ] Done"
    guardrails_content = "# Guardrails\n\nRules"

    (initialized_project / "PROMPT.md").write_text(goal_content)
    (initialized_project / ".ralph" / "handoff.md").write_text("")
    (initialized_project / ".ralph" / "guardrails.md").write_text(guardrails_content)

    goal = read_prompt_md(initialized_project)
    handoff = read_handoff(initialized_project)
    guardrails = read_guardrails(initialized_project)

    assert goal is not None

    # Should not raise an error even with empty handoff
    prompt = assemble_prompt(
        iteration=1,
        max_iter=20,
        done_count=0,
        goal=goal,
        handoff=handoff,
        guardrails=guardrails,
    )

    assert "Test" in prompt
    assert "Rules" in prompt


def test_integration_whitespace_only_files(initialized_project: Path) -> None:
    """Test prompt assembly when handoff/guardrails are whitespace-only."""
    goal_content = "# Goal\n\nTest\n\n# Success\n\n- [ ] Done"

    (initialized_project / "PROMPT.md").write_text(goal_content)
    (initialized_project / ".ralph" / "handoff.md").write_text("   \n\t\n   ")
    (initialized_project / ".ralph" / "guardrails.md").write_text("   \n\t\n   ")

    goal = read_prompt_md(initialized_project)
    handoff = read_handoff(initialized_project)
    guardrails = read_guardrails(initialized_project)

    assert goal is not None
    assert handoff == ""  # strip() returns empty string
    assert guardrails == ""

    # Should not raise an error
    prompt = assemble_prompt(
        iteration=1,
        max_iter=20,
        done_count=0,
        goal=goal,
        handoff=handoff,
        guardrails=guardrails,
    )

    assert "Test" in prompt

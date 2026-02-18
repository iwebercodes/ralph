"""ralph init command."""

from __future__ import annotations

import shutil
from pathlib import Path

import typer

from ralph.commands.global_flags import about_callback, version_callback
from ralph.core.state import (
    GUARDRAILS_TEMPLATE,
    HANDOFF_DIR,
    HANDOFF_TEMPLATE,
    HISTORY_DIR,
    PROMPT_TEMPLATE,
    MultiSpecState,
    Status,
    get_ralph_dir,
    is_initialized,
    write_done_count,
    write_guardrails,
    write_handoff,
    write_iteration,
    write_multi_state,
    write_status,
)
from ralph.output.console import Console


def init(
    version: bool = typer.Option(
        False,
        "--version",
        is_eager=True,
        hidden=True,
        callback=version_callback,
    ),
    about: bool = typer.Option(
        False,
        "--about",
        is_eager=True,
        hidden=True,
        callback=about_callback,
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing .ralph/ directory"),
) -> None:
    """Initialize Ralph in the current directory."""
    root = Path.cwd()
    ralph_dir = get_ralph_dir(root)
    console = Console()

    if is_initialized(root):
        if not force:
            console.error(".ralph/ already exists", "Use --force to reinitialize")
            raise typer.Exit(1)
        shutil.rmtree(ralph_dir)

    # Create directory structure
    ralph_dir.mkdir(parents=True)
    (ralph_dir / HISTORY_DIR).mkdir()
    (ralph_dir / HANDOFF_DIR).mkdir()

    # Initialize state files
    write_status(Status.IDLE, root)
    write_iteration(0, root)
    write_done_count(0, root)
    write_handoff(HANDOFF_TEMPLATE, root)
    write_guardrails(GUARDRAILS_TEMPLATE, root)
    write_multi_state(
        MultiSpecState(
            version=1,
            iteration=0,
            status=Status.IDLE,
            current_index=0,
            specs=[],
        ),
        root,
    )

    # Create PROMPT.md if it doesn't exist
    prompt_path = root / "PROMPT.md"
    created_prompt = False
    if not prompt_path.exists():
        prompt_path.write_text(PROMPT_TEMPLATE)
        created_prompt = True

    if force:
        console.print("Reinitialized Ralph in .ralph/")
    else:
        console.print("Initialized Ralph in .ralph/")

    if created_prompt:
        console.print("Created PROMPT.md template")

    console.print("\nNext steps:")
    console.print("  1. Edit PROMPT.md with your goal")
    console.print("  2. Run: ralph run")

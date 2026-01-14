"""CLI entry point for Ralph."""

from __future__ import annotations

import typer

from ralph.commands.history import history
from ralph.commands.init import init
from ralph.commands.reset import reset
from ralph.commands.run import run
from ralph.commands.status import status
from ralph.output.about import get_about_text


def _main_callback(
    ctx: typer.Context,
    about: bool = typer.Option(
        False,
        "--about",
        help="Show comprehensive explanation of how Ralph works",
    ),
) -> None:
    """Main callback to handle --about flag."""
    if about:
        typer.echo(get_about_text())
        raise typer.Exit(0)
    # If no subcommand and no --about, show help
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(0)


app = typer.Typer(
    name="ralph",
    help="Autonomous development loop with context rotation",
    invoke_without_command=True,
    callback=_main_callback,
)

app.command()(init)
app.command()(run)
app.command()(status)
app.command()(reset)
app.command()(history)

if __name__ == "__main__":
    app()

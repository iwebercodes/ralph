"""CLI entry point for Ralph."""

from __future__ import annotations

import typer

from ralph.commands.history import history
from ralph.commands.init import init
from ralph.commands.reset import reset
from ralph.commands.run import run
from ralph.commands.status import status

app = typer.Typer(
    name="ralph",
    help="Autonomous development loop with context rotation",
    no_args_is_help=True,
)

app.command()(init)
app.command()(run)
app.command()(status)
app.command()(reset)
app.command()(history)

if __name__ == "__main__":
    app()

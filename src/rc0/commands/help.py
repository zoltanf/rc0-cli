"""`rc0 help <topic>` — long-form topic documentation."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from rc0.app_state import AppState  # noqa: TC001
from rc0.client.errors import NotFoundError

app = typer.Typer(
    name="help",
    help="Long-form topic documentation.",
    no_args_is_help=True,
)

# Topics directory sits alongside the commands package, two levels up from this file.
_TOPICS_DIR = Path(__file__).parent.parent / "topics"


def available_topics() -> list[str]:
    """Return the list of ``.md`` topics shipped in the package."""
    if not _TOPICS_DIR.is_dir():
        return []
    return sorted(p.stem for p in _TOPICS_DIR.glob("*.md"))


def _print_topic_list() -> None:
    topics = available_topics()
    if not topics:
        raise NotFoundError(
            "Help topics are not available in this build.",
            hint="Install rc0 from PyPI for full help: pip install rc0-cli",
        )
    for t in topics:
        typer.echo(t)


@app.callback(invoke_without_command=True)
def show(
    ctx: typer.Context,
    topic: Annotated[
        str | None,
        typer.Argument(
            help="Topic name, e.g. 'authentication', or 'list' to enumerate topics.",
        ),
    ] = None,
) -> None:
    """Print the Markdown content of one topic, or list topics if no name given.

    Examples:

      rc0 help list
      rc0 help authentication
      rc0 help output-formats
    """
    state: AppState = ctx.obj  # noqa: F841 — reserved; keeps signature symmetric
    if ctx.invoked_subcommand is not None:
        return
    if topic is None or topic == "list":
        _print_topic_list()
        return
    topic_path = _TOPICS_DIR / f"{topic}.md"
    if not topic_path.is_file():
        raise NotFoundError(
            f"No help topic named {topic!r}.",
            hint=f"Run `rc0 help list` to see available topics: {', '.join(available_topics())}.",
        )
    typer.echo(topic_path.read_text(encoding="utf-8"))

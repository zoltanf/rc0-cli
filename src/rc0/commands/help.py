"""`rc0 help <topic>` — long-form topic documentation."""

from __future__ import annotations

from importlib import resources
from typing import Annotated

import typer

from rc0.app_state import AppState  # noqa: TC001
from rc0.client.errors import NotFoundError

app = typer.Typer(
    name="help",
    help="Long-form topic documentation.",
    no_args_is_help=True,
)

TOPICS_PACKAGE = "rc0.topics"


def available_topics() -> list[str]:
    """Return the list of ``.md`` topics shipped in the package."""
    try:
        topics: list[str] = []
        for entry in resources.files(TOPICS_PACKAGE).iterdir():
            name = entry.name
            if name.endswith(".md"):
                topics.append(name.removesuffix(".md"))
        return sorted(topics)
    except ModuleNotFoundError:
        return []


@app.command("list")
def list_topics(ctx: typer.Context) -> None:
    """Print the topics installed with this rc0 build."""
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
        typer.Argument(help="Topic name, e.g. 'authentication'. Omit to list topics."),
    ] = None,
) -> None:
    """Print the Markdown content of one topic, or list topics if no name given."""
    state: AppState = ctx.obj  # noqa: F841 — reserved; keeps signature symmetric
    if ctx.invoked_subcommand is not None:
        return
    if topic is None:
        for t in available_topics():
            typer.echo(t)
        return
    try:
        data = resources.files(TOPICS_PACKAGE).joinpath(f"{topic}.md").read_text(encoding="utf-8")
    except ModuleNotFoundError as exc:
        raise NotFoundError(
            "Help topics are not available in this build.",
            hint="Install rc0 from PyPI for full help: pip install rc0-cli",
        ) from exc
    except (FileNotFoundError, OSError) as exc:
        raise NotFoundError(
            f"No help topic named {topic!r}.",
            hint=f"Run `rc0 help list` to see available topics: {', '.join(available_topics())}.",
        ) from exc
    typer.echo(data)

"""`rc0 messages` — poll / list queued account messages (Phase 1 read-only)."""

from __future__ import annotations

from typing import Annotated

import typer

from rc0.api import messages as messages_api
from rc0.api import messages_write as messages_write_api
from rc0.app_state import AppState  # noqa: TC001
from rc0.commands._helpers import _client, _render_mutation, _validate_pagination
from rc0.confirm import confirm_yes_no
from rc0.output import render

app = typer.Typer(
    name="messages",
    help="Inspect queued account messages.",
    no_args_is_help=True,
)


PageOpt = Annotated[
    int | None,
    typer.Option("--page", min=1, help="1-indexed page number (incompatible with --all)."),
]
PageSizeOpt = Annotated[
    int | None,
    typer.Option("--page-size", min=1, max=1000, help="Rows per page (default 50)."),
]


@app.command("poll")
def poll_cmd(ctx: typer.Context) -> None:
    """Poll the oldest unacknowledged message. API: GET /api/v2/messages"""
    state: AppState = ctx.obj
    with _client(state) as client:
        msg = messages_api.poll_message(client)
    payload: dict[str, object] = {} if msg is None else msg.model_dump(exclude_none=True)
    typer.echo(render(payload, fmt=state.effective_output))


@app.command("list")
def list_cmd(
    ctx: typer.Context,
    page: PageOpt = None,
    page_size: PageSizeOpt = None,
    fetch_all: Annotated[bool, typer.Option("--all", help="Auto-paginate every row.")] = False,
) -> None:
    """List queued messages. API: GET /api/v2/messages/list

    Examples:

      rc0 messages list
      rc0 -o json messages list --all
    """
    state: AppState = ctx.obj
    _validate_pagination(fetch_all, page)
    with _client(state) as client:
        msgs = messages_api.list_messages(
            client,
            page=page,
            page_size=page_size,
            fetch_all=fetch_all,
        )
    typer.echo(
        render(
            [m.model_dump(exclude_none=True) for m in msgs],
            fmt=state.effective_output,
            columns=["id", "domain", "date", "type", "comment"],
        ),
    )


MessageIdArg = Annotated[int, typer.Argument(help="Message ID to acknowledge.")]


@app.command("ack")
def ack_cmd(ctx: typer.Context, message_id: MessageIdArg) -> None:
    """Acknowledge (delete) one message. API: DELETE /api/v2/messages/{id}"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = messages_write_api.ack_message(
            client,
            message_id=message_id,
            dry_run=state.dry_run,
        )
    _render_mutation(result, state)


@app.command("ack-all")
def ack_all_cmd(ctx: typer.Context) -> None:
    """Loop: poll + ack until the queue is empty. API: GET /messages + DELETE /messages/{id}

    Prompts for confirmation unless -y is passed.

    Examples:

      rc0 messages ack-all
      rc0 messages ack-all -y
      rc0 --dry-run -o json messages ack-all
    """
    state: AppState = ctx.obj
    if state.dry_run:
        # Not a single HTTP call — emit a dry-run envelope with just a summary.
        # The live branch can't know the queue depth without actually draining it.
        typer.echo(
            render(
                {
                    "dry_run": True,
                    "summary": "Would acknowledge every queued account message until empty.",
                    "side_effects": ["drains_message_queue"],
                },
                fmt=state.effective_output,
            ),
        )
        return
    if not state.yes:
        confirm_yes_no("Would acknowledge every queued account message.")
    with _client(state) as client:
        acked = messages_write_api.ack_all(client)
    typer.echo(
        render({"acknowledged": acked, "count": len(acked)}, fmt=state.effective_output),
    )

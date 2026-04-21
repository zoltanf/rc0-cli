"""`rc0 messages` — poll / list queued account messages (Phase 1 read-only)."""

from __future__ import annotations

from typing import Annotated

import typer

from rc0 import auth as auth_core
from rc0.api import messages as messages_api
from rc0.app_state import AppState  # noqa: TC001
from rc0.client.errors import AuthError, ValidationError
from rc0.client.http import Client
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


def _client(state: AppState) -> Client:
    token = state.token
    if token is None:
        record = auth_core.load_token(state.profile_name)
        if record is not None:
            token = auth_core.token_of(record)
    if not token:
        raise AuthError(
            "No API token available.",
            hint=f"Run `rc0 auth login` or set RC0_API_TOKEN (profile {state.profile_name!r}).",
        )
    return Client(
        api_url=state.effective_api_url,
        token=token,
        timeout=state.effective_timeout,
    )


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
    """List queued messages. API: GET /api/v2/messages/list"""
    state: AppState = ctx.obj
    if fetch_all and page is not None:
        raise ValidationError(
            "--page cannot be combined with --all.",
            hint="Use --all to iterate every page, or --page/--page-size to select one page.",
        )
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

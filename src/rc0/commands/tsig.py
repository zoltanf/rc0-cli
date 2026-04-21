"""`rc0 tsig` — list / show + deprecated list-out."""

from __future__ import annotations

from typing import Annotated

import typer

from rc0 import auth as auth_core
from rc0.api import tsig as tsig_api
from rc0.app_state import AppState  # noqa: TC001
from rc0.client.errors import AuthError, ValidationError
from rc0.client.http import Client
from rc0.commands._deprecated import deprecated_warn
from rc0.output import render

app = typer.Typer(name="tsig", help="Manage TSIG keys.", no_args_is_help=True)

NameArg = Annotated[str, typer.Argument(help="TSIG key name.")]
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


@app.command("list")
def list_cmd(
    ctx: typer.Context,
    page: PageOpt = None,
    page_size: PageSizeOpt = None,
    fetch_all: Annotated[bool, typer.Option("--all", help="Auto-paginate every row.")] = False,
) -> None:
    """List TSIG keys. API: GET /api/v2/tsig"""
    state: AppState = ctx.obj
    if fetch_all and page is not None:
        raise ValidationError(
            "--page cannot be combined with --all.",
            hint="Use --all to iterate every page, or --page/--page-size to select one page.",
        )
    with _client(state) as client:
        keys = tsig_api.list_tsig(
            client,
            page=page,
            page_size=page_size,
            fetch_all=fetch_all,
        )
    typer.echo(
        render(
            [k.model_dump(exclude_none=True) for k in keys],
            fmt=state.effective_output,
            columns=["name", "algorithm", "id"],
        ),
    )


@app.command("show")
def show_cmd(ctx: typer.Context, name: NameArg) -> None:
    """Show one TSIG key. API: GET /api/v2/tsig/{keyname}"""
    state: AppState = ctx.obj
    with _client(state) as client:
        k = tsig_api.show_tsig(client, name)
    typer.echo(render(k.model_dump(exclude_none=True), fmt=state.effective_output))


@app.command("list-out", hidden=True)
def list_out_cmd(ctx: typer.Context) -> None:
    """[DEPRECATED] Show the legacy outgoing TSIG key. API: GET /api/v2/tsig/out"""
    deprecated_warn("rc0 tsig list-out")
    state: AppState = ctx.obj
    with _client(state) as client:
        payload = tsig_api.list_tsig_out_deprecated(client)
    typer.echo(render(payload, fmt=state.effective_output))

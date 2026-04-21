"""`rc0 zone` — list / show / status (Phase 1 read-only surface)."""

from __future__ import annotations

from typing import Annotated

import typer

from rc0 import auth as auth_core
from rc0.api import zones as zones_api
from rc0.app_state import AppState  # noqa: TC001
from rc0.client.errors import AuthError
from rc0.client.http import Client
from rc0.output import render

app = typer.Typer(
    name="zone",
    help="Manage RcodeZero zones.",
    no_args_is_help=True,
)


ZoneArg = Annotated[str, typer.Argument(help="Fully-qualified zone apex, e.g. example.com.")]
PageOpt = Annotated[int | None, typer.Option("--page", help="1-indexed page number.")]
PageSizeOpt = Annotated[int | None, typer.Option("--page-size", help="Rows per page (default 50).")]
AllOpt = Annotated[bool, typer.Option("--all", help="Auto-paginate every row.")]


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
    all: AllOpt = False,
) -> None:
    """List zones on the account. API: GET /api/v2/zones"""
    state: AppState = ctx.obj
    with _client(state) as client:
        zones = zones_api.list_zones(client, page=page, page_size=page_size, all=all)
    payload = [z.model_dump(exclude_none=True) for z in zones]
    typer.echo(
        render(
            payload,
            fmt=state.effective_output,
            columns=["domain", "type", "dnssec"],
        ),
    )


@app.command("show")
def show_cmd(ctx: typer.Context, zone: ZoneArg) -> None:
    """Show one zone. API: GET /api/v2/zones/{zone}"""
    state: AppState = ctx.obj
    with _client(state) as client:
        z = zones_api.show_zone(client, zone)
    typer.echo(render(z.model_dump(exclude_none=True), fmt=state.effective_output))


@app.command("status")
def status_cmd(ctx: typer.Context, zone: ZoneArg) -> None:
    """Show a zone's operational status. API: GET /api/v2/zones/{zone}/status"""
    state: AppState = ctx.obj
    with _client(state) as client:
        s = zones_api.zone_status(client, zone)
    typer.echo(render(s.model_dump(exclude_none=True), fmt=state.effective_output))

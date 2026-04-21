"""`rc0 record` — list / export (Phase 1 read-only surface)."""

from __future__ import annotations

from typing import Annotated

import typer

from rc0 import auth as auth_core
from rc0.api import rrsets as rrsets_api
from rc0.app_state import AppState  # noqa: TC001
from rc0.client.errors import AuthError, ValidationError
from rc0.client.http import Client
from rc0.output import OutputFormat, render
from rc0.output.bind import render_rrsets

app = typer.Typer(name="record", help="Manage RRsets.", no_args_is_help=True)

ZoneArg = Annotated[str, typer.Argument(help="Zone apex, e.g. example.com.")]


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
    zone: ZoneArg,
    name: Annotated[
        str | None,
        typer.Option("--name", help="Filter by RR name."),
    ] = None,
    type_: Annotated[
        str | None,
        typer.Option("--type", help="Filter by RR type."),
    ] = None,
    page: Annotated[
        int | None,
        typer.Option("--page", min=1, help="1-indexed page number (incompatible with --all)."),
    ] = None,
    page_size: Annotated[
        int | None,
        typer.Option("--page-size", min=1, max=1000, help="Rows per page (default 50)."),
    ] = None,
    fetch_all: Annotated[
        bool,
        typer.Option("--all", help="Auto-paginate every row."),
    ] = False,
) -> None:
    """List RRsets. API: GET /api/v2/zones/{zone}/rrsets"""
    state: AppState = ctx.obj
    if fetch_all and page is not None:
        raise ValidationError(
            "--page cannot be combined with --all.",
            hint="Use --all to iterate every page, or --page/--page-size to select one page.",
        )
    with _client(state) as client:
        rows = rrsets_api.list_rrsets(
            client,
            zone,
            name=name,
            type=type_,
            page=page,
            page_size=page_size,
            fetch_all=fetch_all,
        )
    typer.echo(
        render(
            [r.model_dump(exclude_none=True) for r in rows],
            fmt=state.effective_output,
            columns=["name", "type", "ttl", "records"],
        ),
    )


@app.command("export")
def export_cmd(
    ctx: typer.Context,
    zone: ZoneArg,
    fmt: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format: bind (default), json, or yaml.",
            case_sensitive=False,
        ),
    ] = "bind",
) -> None:
    """Export every RRset in a zone. API: GET /api/v2/zones/{zone}/rrsets"""
    state: AppState = ctx.obj
    fmt_lower = fmt.lower()
    if fmt_lower not in {"bind", "json", "yaml"}:
        raise ValidationError(
            f"Unsupported --format {fmt!r}.",
            hint="Valid formats: bind, json, yaml.",
        )
    with _client(state) as client:
        rows = rrsets_api.list_rrsets(client, zone, fetch_all=True)
    payload = [r.model_dump(exclude_none=True) for r in rows]
    if fmt_lower == "bind":
        typer.echo(render_rrsets(zone=zone, rrsets=payload))
    else:
        typer.echo(render(payload, fmt=OutputFormat(fmt_lower)))

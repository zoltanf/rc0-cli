"""`rc0 report` — account-level reports (Phase 1 read-only surface).

``problematic-zones`` is Laravel-paginated and exposes the standard
``--page``/``--page-size``/``--all`` flag trio. The other report endpoints
return bare arrays with server-side filters (``--day``, ``--month``,
``--include-nx``).
"""

from __future__ import annotations

from typing import Annotated

import typer

from rc0 import auth as auth_core
from rc0.api import reports as reports_api
from rc0.app_state import AppState  # noqa: TC001
from rc0.client.errors import AuthError, ValidationError
from rc0.client.http import Client
from rc0.output import render

app = typer.Typer(name="report", help="Account-level reports.", no_args_is_help=True)


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


@app.command("problematic-zones")
def problematic_zones_cmd(
    ctx: typer.Context,
    page: PageOpt = None,
    page_size: PageSizeOpt = None,
    fetch_all: Annotated[bool, typer.Option("--all", help="Auto-paginate every row.")] = False,
) -> None:
    """Zones currently flagged with problems. API: GET /api/v2/reports/problematiczones"""
    state: AppState = ctx.obj
    if fetch_all and page is not None:
        raise ValidationError(
            "--page cannot be combined with --all.",
            hint="Use --all to iterate every page, or --page/--page-size to select one page.",
        )
    with _client(state) as client:
        rows = reports_api.list_problematic_zones(
            client,
            page=page,
            page_size=page_size,
            fetch_all=fetch_all,
        )
    typer.echo(
        render(
            [r.model_dump(exclude_none=True) for r in rows],
            fmt=state.effective_output,
        ),
    )


@app.command("nxdomains")
def nxdomains_cmd(
    ctx: typer.Context,
    day: Annotated[
        str | None,
        typer.Option("--day", help="Filter: 'today' or 'yesterday'."),
    ] = None,
) -> None:
    """NXDOMAIN report. API: GET /api/v2/reports/nxdomains"""
    state: AppState = ctx.obj
    with _client(state) as client:
        rows = reports_api.list_nxdomains(client, day=day)
    typer.echo(
        render(
            [r.model_dump(exclude_none=True) for r in rows],
            fmt=state.effective_output,
            columns=["date", "domain", "qname", "qtype", "querycount"],
        ),
    )


@app.command("accounting")
def accounting_cmd(
    ctx: typer.Context,
    month: Annotated[
        str | None,
        typer.Option("--month", help="Filter by month, e.g. '2026-04'."),
    ] = None,
) -> None:
    """Monthly accounting report. API: GET /api/v2/reports/accounting"""
    state: AppState = ctx.obj
    with _client(state) as client:
        rows = reports_api.list_accounting(client, month=month)
    typer.echo(
        render(
            [r.model_dump(exclude_none=True) for r in rows],
            fmt=state.effective_output,
            columns=[
                "account",
                "date",
                "domain_count",
                "domain_count_dnssec",
                "query_count",
                "records_count",
            ],
        ),
    )


@app.command("queryrates")
def queryrates_cmd(
    ctx: typer.Context,
    month: Annotated[
        str | None,
        typer.Option("--month", help="Filter by month, e.g. '2026-04'."),
    ] = None,
    day: Annotated[
        str | None,
        typer.Option("--day", help="Filter: 'today' or 'yesterday'."),
    ] = None,
    include_nx: Annotated[
        bool,
        typer.Option("--include-nx", help="Include NXDOMAIN counts."),
    ] = False,
) -> None:
    """Per-zone query rates. API: GET /api/v2/reports/queryrates"""
    state: AppState = ctx.obj
    with _client(state) as client:
        rows = reports_api.list_queryrates(
            client,
            month=month,
            day=day,
            include_nx=include_nx,
        )
    typer.echo(
        render(
            [r.model_dump(exclude_none=True) for r in rows],
            fmt=state.effective_output,
            columns=["date", "domain", "querycount", "nx_querycount"],
        ),
    )


@app.command("domainlist")
def domainlist_cmd(ctx: typer.Context) -> None:
    """List all domains on the account with serials. API: GET /api/v2/reports/domainlist"""
    state: AppState = ctx.obj
    with _client(state) as client:
        rows = reports_api.list_domainlist(client)
    typer.echo(
        render(
            [r.model_dump(exclude_none=True) for r in rows],
            fmt=state.effective_output,
            columns=["domain", "serial"],
        ),
    )

"""`rc0 report` — account-level reports (Phase 1 read-only surface).

``problematic-zones`` is Laravel-paginated and exposes the standard
``--page``/``--page-size``/``--all`` flag trio. The other report endpoints
return bare arrays with server-side filters (``--day``, ``--month``,
``--include-nx``).
"""

from __future__ import annotations

from typing import Annotated

import typer

from rc0.api import reports as reports_api
from rc0.app_state import AppState  # noqa: TC001
from rc0.commands._helpers import _client, _validate_pagination
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

_DAY_HELP = "Filter by day: 'today', 'yesterday', or YYYY-MM-DD."


@app.command("problematic-zones")
def problematic_zones_cmd(
    ctx: typer.Context,
    page: PageOpt = None,
    page_size: PageSizeOpt = None,
    fetch_all: Annotated[bool, typer.Option("--all", help="Auto-paginate every row.")] = False,
) -> None:
    """Zones currently flagged with problems. API: GET /api/v2/reports/problematiczones"""
    state: AppState = ctx.obj
    _validate_pagination(fetch_all, page)
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
        typer.Option("--day", help=_DAY_HELP),
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
        typer.Option("--month", help="Filter by month, e.g. '2026-04'. Required if --day omitted."),
    ] = None,
    day: Annotated[
        str | None,
        typer.Option("--day", help=f"{_DAY_HELP} Required if --month is omitted."),
    ] = None,
    include_nx: Annotated[
        bool,
        typer.Option("--include-nx", help="Include NXDOMAIN counts."),
    ] = False,
) -> None:
    """Per-zone query rates. API: GET /api/v2/reports/queryrates"""
    if month is None and day is None:
        raise typer.BadParameter(
            "Provide either --day (e.g. 'today', 'YYYY-MM-DD') or --month (e.g. '2026-04').",
            param_hint="'--day' / '--month'",
        )
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

"""`rc0 report` — account-level reports (Phase 1 read-only surface).

``problematic-zones`` is Laravel-paginated and exposes the standard
``--page``/``--page-size``/``--all`` flag trio. The other report endpoints
return bare arrays with server-side filters (``--day``, ``--month``,
``--include-nx``).
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

import typer

from rc0.api import reports as reports_api
from rc0.app_state import AppState  # noqa: TC001
from rc0.commands._helpers import _client, _validate_pagination, _warn_if_truncated
from rc0.output import render

app = typer.Typer(name="report", help="Account-level reports.", no_args_is_help=True)


PageOpt = Annotated[
    int | None,
    typer.Option(
        "--page",
        min=1,
        help="Fetch only this 1-indexed page. Omit to fetch every row.",
    ),
]
PageSizeOpt = Annotated[
    int | None,
    typer.Option(
        "--page-size",
        min=1,
        max=1000,
        help="Rows per HTTP request (default 50).",
    ),
]

_DAY_HELP = "Filter by day: 'today', 'yesterday', or YYYY-MM-DD (e.g. 2026-04-22)."
_NXDOMAIN_DAY_HELP = (
    "Filter by day: 'today' or 'yesterday' (the API does not accept explicit dates)."
)


def _validate_day(day: str | None) -> None:
    if day is None or day in ("today", "yesterday"):
        return
    try:
        date.fromisoformat(day)
    except ValueError as err:
        raise typer.BadParameter(
            f"{day!r} is not a recognised day value. Use 'today', 'yesterday', or YYYY-MM-DD.",
            param_hint="'--day'",
        ) from err


def _validate_nxdomain_day(day: str | None) -> None:
    if day is None or day in ("today", "yesterday"):
        return
    raise typer.BadParameter(
        f"{day!r} is not supported. The nxdomains endpoint only accepts 'today' or 'yesterday'.",
        param_hint="'--day'",
    )


@app.command("problematic-zones")
def problematic_zones_cmd(
    ctx: typer.Context,
    page: PageOpt = None,
    page_size: PageSizeOpt = None,
    fetch_all: Annotated[
        bool,
        typer.Option(
            "--all",
            help="[kept for compatibility] fetching every row is now the default.",
        ),
    ] = False,
) -> None:
    """Zones currently flagged with problems. API: GET /api/v2/reports/problematiczones

    Fetches every row by default. Use ``--page N`` for a single page.
    """
    state: AppState = ctx.obj
    _validate_pagination(fetch_all, page)
    with _client(state) as client:
        if page is not None:
            rows, info = reports_api.list_problematic_zones_page(
                client,
                page=page,
                page_size=page_size,
            )
        else:
            rows = reports_api.list_problematic_zones(
                client,
                page_size=page_size,
                fetch_all=True,
            )
            info = None
    typer.echo(
        render(
            [r.model_dump(exclude_none=True) for r in rows],
            fmt=state.effective_output,
        ),
    )
    if info is not None:
        _warn_if_truncated(state, rows, info)


@app.command("nxdomains")
def nxdomains_cmd(
    ctx: typer.Context,
    day: Annotated[
        str | None,
        typer.Option("--day", help=_NXDOMAIN_DAY_HELP),
    ] = None,
    zone: Annotated[
        str | None,
        typer.Option(
            "--zone",
            help="Filter results to a single zone apex (client-side; trailing dot ignored).",
        ),
    ] = None,
) -> None:
    """NXDOMAIN report. API: GET /api/v2/reports/nxdomains

    Columns: date, domain, qname, qtype, querycount.

    The API itself has no zone parameter for this endpoint, so --zone
    is applied client-side after fetching the full account-wide report.

    Examples:

      rc0 report nxdomains
      rc0 report nxdomains --day yesterday
      rc0 report nxdomains --zone example.com
    """
    _validate_nxdomain_day(day)
    state: AppState = ctx.obj
    with _client(state) as client:
        rows = reports_api.list_nxdomains(client, day=day)
    if zone is not None:
        target = zone.rstrip(".")
        rows = [r for r in rows if (r.domain or "").rstrip(".") == target]
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
    _validate_day(day)
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

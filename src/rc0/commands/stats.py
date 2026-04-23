"""`rc0 stats` — account + per-zone statistics (Phase 1 read-only surface).

All stats endpoints return bare arrays. None paginate, so these commands
expose neither ``--page`` nor ``--all``. Deprecated endpoints are hidden
from ``--help`` and emit a ``[DEPRECATED]`` banner on stderr.
"""

from __future__ import annotations

from typing import Annotated

import typer

from rc0.api import stats as stats_api
from rc0.app_state import AppState  # noqa: TC001
from rc0.commands._deprecated import deprecated_warn
from rc0.commands._helpers import _client
from rc0.output import render

app = typer.Typer(name="stats", help="Account statistics.", no_args_is_help=True)
zone_app = typer.Typer(name="zone", help="Per-zone statistics.", no_args_is_help=True)
app.add_typer(zone_app, name="zone")


ZoneArg = Annotated[str, typer.Argument(help="Fully-qualified zone apex, e.g. example.com.")]

DaysOpt = Annotated[
    int | None,
    typer.Option(
        "--days",
        min=1,
        max=180,
        help="Lookback window in days (1-180). API default is 30.",
    ),
]


# ----------------------------------------------------------- top-level (live)


@app.command("queries")
def queries_cmd(ctx: typer.Context, days: DaysOpt = None) -> None:
    """Query counts per day. API: GET /api/v2/stats/querycounts

    Columns: date, count (total queries), nxcount (NXDOMAIN responses).

    Examples:

      rc0 stats queries
      rc0 stats queries --days 7
      rc0 -o tsv stats queries --days 30
    """
    state: AppState = ctx.obj
    with _client(state) as client:
        rows = stats_api.list_querycounts(client, days=days)
    typer.echo(
        render(
            [r.model_dump(exclude_none=True) for r in rows],
            fmt=state.effective_output,
            columns=["date", "count", "nxcount"],
        ),
    )


@app.command("topzones")
def topzones_cmd(ctx: typer.Context, days: DaysOpt = None) -> None:
    """Top zones by traffic. API: GET /api/v2/stats/topzones

    Returns up to 1000 zones ranked by query count over the lookback
    window. Columns: domain, qc (query count).

    Examples:

      rc0 stats topzones
      rc0 stats topzones --days 7
    """
    state: AppState = ctx.obj
    with _client(state) as client:
        rows = stats_api.list_topzones(client, days=days)
    typer.echo(
        render(
            [r.model_dump(exclude_none=True) for r in rows],
            fmt=state.effective_output,
        ),
    )


@app.command("countries")
def countries_cmd(ctx: typer.Context) -> None:
    """Query counts per country. API: GET /api/v2/stats/countries"""
    state: AppState = ctx.obj
    with _client(state) as client:
        rows = stats_api.list_countries(client)
    typer.echo(
        render(
            [r.model_dump(exclude_none=True) for r in rows],
            fmt=state.effective_output,
            columns=["cc", "country", "qc", "region", "subregion"],
        ),
    )


# ----------------------------------------------------- top-level (deprecated)


@app.command("topmagnitude", hidden=True)
def topmagnitude_cmd(ctx: typer.Context) -> None:
    """[DEPRECATED] Top magnitude. API: GET /api/v2/stats/topmagnitude"""
    deprecated_warn("rc0 stats topmagnitude")
    state: AppState = ctx.obj
    with _client(state) as client:
        rows = stats_api.list_topmagnitude(client)
    typer.echo(
        render(
            [r.model_dump(exclude_none=True) for r in rows],
            fmt=state.effective_output,
        ),
    )


@app.command("topnxdomains", hidden=True)
def topnxdomains_cmd(ctx: typer.Context) -> None:
    """[DEPRECATED] Top NXDOMAIN qnames. API: GET /api/v2/stats/topnxdomains"""
    deprecated_warn("rc0 stats topnxdomains")
    state: AppState = ctx.obj
    with _client(state) as client:
        rows = stats_api.list_topnxdomains(client)
    typer.echo(
        render(
            [r.model_dump(exclude_none=True) for r in rows],
            fmt=state.effective_output,
        ),
    )


@app.command("topqnames", hidden=True)
def topqnames_cmd(ctx: typer.Context) -> None:
    """[DEPRECATED] Top qnames. API: GET /api/v2/stats/topqnames"""
    deprecated_warn("rc0 stats topqnames")
    state: AppState = ctx.obj
    with _client(state) as client:
        rows = stats_api.list_topqnames(client)
    typer.echo(
        render(
            [r.model_dump(exclude_none=True) for r in rows],
            fmt=state.effective_output,
        ),
    )


# -------------------------------------------------- zone subgroup (live)


@zone_app.command("queries")
def zone_queries_cmd(ctx: typer.Context, zone: ZoneArg, days: DaysOpt = None) -> None:
    """Query counts for one zone. API: GET /api/v2/zones/{zone}/stats/queries

    Columns: date, qcount (total queries), nxcount (NXDOMAIN responses).

    The API always returns the full 180-day history; --days N keeps
    only the most recent N days client-side.

    Examples:

      rc0 stats zone queries example.com
      rc0 stats zone queries example.com --days 7
    """
    state: AppState = ctx.obj
    with _client(state) as client:
        rows = stats_api.list_zone_queries(client, zone)
    if days is not None:
        rows = sorted(rows, key=lambda r: r.date or "")[-days:]
    typer.echo(
        render(
            [r.model_dump(exclude_none=True) for r in rows],
            fmt=state.effective_output,
            columns=["date", "qcount", "nxcount"],
        ),
    )


# --------------------------------------------- zone subgroup (deprecated)


@zone_app.command("magnitude", hidden=True)
def zone_magnitude_cmd(ctx: typer.Context, zone: ZoneArg) -> None:
    """[DEPRECATED] Magnitude per zone. API: GET /api/v2/zones/{zone}/stats/magnitude"""
    deprecated_warn("rc0 stats zone magnitude")
    state: AppState = ctx.obj
    with _client(state) as client:
        rows = stats_api.list_zone_magnitude(client, zone)
    typer.echo(
        render(
            [r.model_dump(exclude_none=True) for r in rows],
            fmt=state.effective_output,
            columns=["date", "mag"],
        ),
    )


@zone_app.command("nxdomains", hidden=True)
def zone_nxdomains_cmd(ctx: typer.Context, zone: ZoneArg) -> None:
    """[DEPRECATED] NXDOMAIN qnames per zone.

    API: GET /api/v2/zones/{zone}/stats/nxdomains
    """
    deprecated_warn("rc0 stats zone nxdomains")
    state: AppState = ctx.obj
    with _client(state) as client:
        rows = stats_api.list_zone_nxdomains(client, zone)
    typer.echo(
        render(
            [r.model_dump(exclude_none=True) for r in rows],
            fmt=state.effective_output,
        ),
    )


@zone_app.command("qnames", hidden=True)
def zone_qnames_cmd(ctx: typer.Context, zone: ZoneArg) -> None:
    """[DEPRECATED] Top qnames per zone. API: GET /api/v2/zones/{zone}/stats/qnames"""
    deprecated_warn("rc0 stats zone qnames")
    state: AppState = ctx.obj
    with _client(state) as client:
        rows = stats_api.list_zone_qnames(client, zone)
    typer.echo(
        render(
            [r.model_dump(exclude_none=True) for r in rows],
            fmt=state.effective_output,
        ),
    )

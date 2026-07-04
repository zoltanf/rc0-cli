"""`rc0 sites` — list RcodeZero anycast locations (read-only)."""

from __future__ import annotations

import typer

from rc0.api import sites as sites_api
from rc0.app_state import AppState  # noqa: TC001
from rc0.commands._helpers import _client
from rc0.output import render

app = typer.Typer(name="sites", help="List RcodeZero anycast locations.", no_args_is_help=True)


@app.callback()
def _callback() -> None:
    """Force Typer to keep ``sites`` a command group.

    A Typer app with a single command collapses into that command unless a
    callback is present; ``rc0.app`` requires every subapp to resolve to a
    ``click.Group``.
    """


@app.command("list")
def list_cmd(ctx: typer.Context) -> None:
    """List RcodeZero anycast locations. API: GET /api/v2/sites

    Columns: name, city, countrycode, continent, latitude, longitude,
    status, clouds.
    """
    state: AppState = ctx.obj
    with _client(state) as client:
        rows = sites_api.list_sites(client)
    typer.echo(
        render(
            [r.model_dump(exclude_none=True) for r in rows],
            fmt=state.effective_output,
            columns=[
                "name",
                "city",
                "countrycode",
                "continent",
                "latitude",
                "longitude",
                "status",
                "clouds",
            ],
        ),
    )

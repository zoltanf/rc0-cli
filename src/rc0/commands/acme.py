"""`rc0 acme` — ACME DNS-01 challenge management (v1 API)."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Annotated

import typer

from rc0.api import acme as acme_api
from rc0.api import acme_write
from rc0.app_state import AppState  # noqa: TC001
from rc0.client.errors import AuthzError
from rc0.commands._helpers import _client, _render_mutation
from rc0.confirm import confirm_yes_no
from rc0.output import render

if TYPE_CHECKING:
    from collections.abc import Generator

    from rc0.client.http import Client

app = typer.Typer(name="acme", help="Manage ACME DNS-01 challenge records.", no_args_is_help=True)

_ACME_403_HINT = (
    "ACME endpoints require a token with the ACME permission. "
    "Manage your API tokens at https://my.rcodezero.at/."
)

ZoneArg = Annotated[str, typer.Argument(help="Fully-qualified zone apex, e.g. example.com.")]


@contextmanager
def _acme_client(state: AppState) -> Generator[Client]:
    with _client(state) as client:
        try:
            yield client
        except AuthzError as exc:
            raise AuthzError(
                exc.message,
                hint=_ACME_403_HINT,
                http_status=exc.http_status,
                request=exc.request,
            ) from exc


# ------------------------------------------------------------------- commands


@app.command("zone-exists")
def zone_exists_cmd(ctx: typer.Context, zone: ZoneArg) -> None:
    """Check if a zone is configured for ACME. API: GET /api/v1/acme/{zone}

    Examples:

      rc0 acme zone-exists example.com
      rc0 -o json acme zone-exists example.com
    """
    state: AppState = ctx.obj
    with _acme_client(state) as client:
        result = acme_api.zone_exists(client, zone)
    typer.echo(render(result, fmt=state.effective_output))


@app.command("list-challenges")
def list_challenges_cmd(
    ctx: typer.Context,
    zone: ZoneArg,
    page: Annotated[
        int | None,
        typer.Option("--page", min=1, help="1-indexed page number (incompatible with --all)."),
    ] = None,
    page_size: Annotated[
        int | None,
        typer.Option("--page-size", min=1, max=10000, help="Rows per page (default 100)."),
    ] = None,
    fetch_all: Annotated[bool, typer.Option("--all", help="Auto-paginate every page.")] = False,
) -> None:
    """List ACME challenge TXT records for a zone. API: GET /api/v1/acme/zones/{zone}/rrsets

    Examples:

      rc0 acme list-challenges example.com
      rc0 -o json acme list-challenges example.com
    """
    state: AppState = ctx.obj
    with _acme_client(state) as client:
        records = acme_api.list_challenges(
            client,
            zone,
            page=page,
            page_size=page_size,
            fetch_all=fetch_all,
        )
    typer.echo(render(records, fmt=state.effective_output))


@app.command("add-challenge")
def add_challenge_cmd(
    ctx: typer.Context,
    zone: ZoneArg,
    value: Annotated[str, typer.Option("--value", help="Challenge token value.")],
    ttl: Annotated[int, typer.Option("--ttl", min=1, help="TTL in seconds.")] = 60,
) -> None:
    """Add an ACME DNS-01 challenge TXT record. API: PATCH /api/v1/acme/zones/{zone}/rrsets

    Requires an ACME-scoped token (see `rc0 help authentication`).

    Examples:

      rc0 acme add-challenge example.com --value abc123token
      rc0 acme add-challenge example.com --value abc123token --ttl 120
      rc0 --dry-run -o json acme add-challenge example.com --value abc123token
    """
    state: AppState = ctx.obj
    with _acme_client(state) as client:
        result = acme_write.add_challenge(
            client,
            zone=zone,
            token=value,
            ttl=ttl,
            dry_run=state.dry_run,
        )
    _render_mutation(result, state)


@app.command("remove-challenge")
def remove_challenge_cmd(ctx: typer.Context, zone: ZoneArg) -> None:
    """Remove ACME challenge TXT records from a zone. API: PATCH /api/v1/acme/zones/{zone}/rrsets

    Prompts for confirmation unless -y is passed.

    Examples:

      rc0 acme remove-challenge example.com
      rc0 acme remove-challenge example.com -y
      rc0 --dry-run -o json acme remove-challenge example.com
    """
    state: AppState = ctx.obj
    if not state.dry_run and not state.yes:
        confirm_yes_no(f"Remove all ACME challenge TXT records from {zone}?")
    with _acme_client(state) as client:
        result = acme_write.remove_challenge(client, zone=zone, dry_run=state.dry_run)
    _render_mutation(result, state)

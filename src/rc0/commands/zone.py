"""`rc0 zone` — list / show / status (Phase 1 read-only surface)."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

import typer

from rc0 import auth as auth_core
from rc0.api import zones as zones_api
from rc0.api import zones_write as zones_write_api
from rc0.app_state import AppState  # noqa: TC001
from rc0.client.dry_run import DryRunResult
from rc0.client.errors import AuthError, ValidationError
from rc0.client.http import Client
from rc0.confirm import confirm_typed
from rc0.output import render

app = typer.Typer(
    name="zone",
    help="Manage RcodeZero zones.",
    no_args_is_help=True,
)


ZoneArg = Annotated[str, typer.Argument(help="Fully-qualified zone apex, e.g. example.com.")]
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
    """List zones on the account. API: GET /api/v2/zones

    Examples:

      rc0 zone list
      rc0 zone list -o json --all
      rc0 zone list --page 2 --page-size 20
    """
    state: AppState = ctx.obj
    if fetch_all and page is not None:
        raise ValidationError(
            "--page cannot be combined with --all.",
            hint="Use --all to iterate every page, or --page/--page-size to select one page.",
        )
    with _client(state) as client:
        zones = zones_api.list_zones(
            client,
            page=page,
            page_size=page_size,
            fetch_all=fetch_all,
        )
    payload = [z.model_dump(exclude_none=True) for z in zones]
    typer.echo(
        render(
            payload,
            fmt=state.effective_output,
            columns=["domain", "type", "serial", "dnssec", "last_check"],
        ),
    )


@app.command("show")
def show_cmd(ctx: typer.Context, zone: ZoneArg) -> None:
    """Show one zone. API: GET /api/v2/zones/{zone}

    Examples:

      rc0 zone show example.com
      rc0 zone show example.com -o json
    """
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


# ---------------------------------------------------------- Phase 2 mutations


class ZoneTypeChoice(StrEnum):
    """Typer-friendly enum. Values match the API's lowercase `type2` enum."""

    master = "master"
    slave = "slave"


TypeOpt = Annotated[
    ZoneTypeChoice,
    typer.Option(
        "--type",
        help="Zone type: master or slave.",
        case_sensitive=False,
    ),
]
MasterOpt = Annotated[
    list[str] | None,
    typer.Option(
        "--master",
        help="Primary nameserver IP. Repeat for multiple; required for slave zones.",
    ),
]
CdsOpt = Annotated[
    bool | None,
    typer.Option(
        "--cds/--no-cds",
        help="Publish CDS/CDNSKEY records (RFC 7344).",
    ),
]
SerialAutoOpt = Annotated[
    bool | None,
    typer.Option(
        "--serial-auto/--no-serial-auto",
        help="Auto-increment serial on RRset updates (master zones only).",
    ),
]
RequiredTsigKeyOpt = Annotated[
    str,
    typer.Option("--tsigkey", help="Name of a preconfigured TSIG key."),
]


def _render_mutation(result: DryRunResult | dict[str, object], state: AppState) -> None:
    payload = result.to_dict() if isinstance(result, DryRunResult) else result
    typer.echo(render(payload, fmt=state.effective_output))


@app.command("create")
def create_cmd(
    ctx: typer.Context,
    domain: Annotated[str, typer.Argument(help="Domain to add.")],
    zone_type: TypeOpt = ZoneTypeChoice.master,
    masters: MasterOpt = None,
    cds: CdsOpt = None,
    serial_auto: SerialAutoOpt = None,
) -> None:
    """Add a new zone. API: POST /api/v2/zones

    Examples:

      rc0 zone create example.com
      rc0 zone create example.com --type slave --master 1.2.3.4
      rc0 zone create example.com --dry-run -o json
    """
    state: AppState = ctx.obj
    with _client(state) as client:
        result = zones_write_api.create_zone(
            client,
            domain=domain,
            zone_type=zone_type.value,
            masters=masters,
            cds_cdnskey_publish=cds,
            serial_auto_increment=serial_auto,
            dry_run=state.dry_run,
        )
    _render_mutation(result, state)


@app.command("update")
def update_cmd(
    ctx: typer.Context,
    zone: ZoneArg,
    zone_type: Annotated[
        ZoneTypeChoice | None,
        typer.Option("--type", help="Change zone type.", case_sensitive=False),
    ] = None,
    masters: MasterOpt = None,
    cds: CdsOpt = None,
    serial_auto: SerialAutoOpt = None,
) -> None:
    """Update an existing zone. API: PUT /api/v2/zones/{zone}

    Examples:

      rc0 zone update example.com --cds
      rc0 zone update example.com --serial-auto
      rc0 zone update example.com --dry-run -o json
    """
    state: AppState = ctx.obj
    with _client(state) as client:
        result = zones_write_api.update_zone(
            client,
            zone=zone,
            zone_type=zone_type.value if zone_type else None,
            masters=masters,
            cds_cdnskey_publish=cds,
            serial_auto_increment=serial_auto,
            dry_run=state.dry_run,
        )
    _render_mutation(result, state)


@app.command("enable")
def enable_cmd(ctx: typer.Context, zone: ZoneArg) -> None:
    """Re-enable a disabled zone. API: PATCH /api/v2/zones/{zone}"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = zones_write_api.patch_zone_disabled(
            client,
            zone=zone,
            disabled=False,
            dry_run=state.dry_run,
        )
    _render_mutation(result, state)


@app.command("disable")
def disable_cmd(ctx: typer.Context, zone: ZoneArg) -> None:
    """Disable a zone without deleting it. API: PATCH /api/v2/zones/{zone}"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = zones_write_api.patch_zone_disabled(
            client,
            zone=zone,
            disabled=True,
            dry_run=state.dry_run,
        )
    _render_mutation(result, state)


@app.command("delete")
def delete_cmd(ctx: typer.Context, zone: ZoneArg) -> None:
    """Delete a zone. API: DELETE /api/v2/zones/{zone}

    Prompts for confirmation (type the zone name) unless -y is passed.

    Examples:

      rc0 zone delete example.com
      rc0 zone delete example.com -y
      rc0 zone delete example.com --dry-run -o json
    """
    state: AppState = ctx.obj
    if not state.dry_run and not state.yes:
        confirm_typed(
            zone,
            summary=f"Would delete zone {zone} and discard every RRset. This cannot be undone.",
        )
    with _client(state) as client:
        result = zones_write_api.delete_zone(
            client,
            zone=zone,
            dry_run=state.dry_run,
        )
    _render_mutation(result, state)


@app.command("retrieve")
def retrieve_cmd(ctx: typer.Context, zone: ZoneArg) -> None:
    """Queue an immediate zone transfer. API: POST /api/v2/zones/{zone}/retrieve"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = zones_write_api.retrieve_zone(
            client,
            zone=zone,
            dry_run=state.dry_run,
        )
    _render_mutation(result, state)


@app.command("test")
def test_cmd(
    ctx: typer.Context,
    domain: Annotated[str, typer.Argument(help="Domain to validate.")],
    zone_type: TypeOpt = ZoneTypeChoice.master,
    masters: MasterOpt = None,
) -> None:
    """Server-side validation (does NOT create). API: POST /api/v2/zones?test=1

    This is distinct from --dry-run: the API runs its own checks against the
    would-be zone. Use --dry-run on top to show what this command would send
    without contacting the API at all.
    """
    state: AppState = ctx.obj
    with _client(state) as client:
        result = zones_write_api.test_zone(
            client,
            domain=domain,
            zone_type=zone_type.value,
            masters=masters,
            dry_run=state.dry_run,
        )
    _render_mutation(result, state)


# -------------------------------------------------------- xfr-in / xfr-out subgroups

xfr_in = typer.Typer(name="xfr-in", help="Per-zone inbound transfer config.", no_args_is_help=True)
xfr_out = typer.Typer(
    name="xfr-out", help="Per-zone outbound transfer config.", no_args_is_help=True
)
app.add_typer(xfr_in, name="xfr-in")
app.add_typer(xfr_out, name="xfr-out")


@xfr_in.command("show")
def xfr_in_show(ctx: typer.Context, zone: ZoneArg) -> None:
    """Show the zone's inbound TSIG config. API: GET /api/v2/zones/{zone}/inbound"""
    state: AppState = ctx.obj
    with _client(state) as client:
        payload = zones_write_api.show_inbound(client, zone=zone)
    typer.echo(render(payload, fmt=state.effective_output))


@xfr_in.command("set")
def xfr_in_set(
    ctx: typer.Context,
    zone: ZoneArg,
    tsigkey: RequiredTsigKeyOpt,
) -> None:
    """Set the inbound TSIG key. API: POST /api/v2/zones/{zone}/inbound"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = zones_write_api.set_inbound(
            client,
            zone=zone,
            tsigkey=tsigkey,
            dry_run=state.dry_run,
        )
    _render_mutation(result, state)


@xfr_in.command("unset")
def xfr_in_unset(ctx: typer.Context, zone: ZoneArg) -> None:
    """Clear the inbound TSIG key. API: DELETE /api/v2/zones/{zone}/inbound"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = zones_write_api.unset_inbound(
            client,
            zone=zone,
            dry_run=state.dry_run,
        )
    _render_mutation(result, state)


@xfr_out.command("show")
def xfr_out_show(ctx: typer.Context, zone: ZoneArg) -> None:
    """Show the zone's outbound xfr config. API: GET /api/v2/zones/{zone}/outbound"""
    state: AppState = ctx.obj
    with _client(state) as client:
        payload = zones_write_api.show_outbound(client, zone=zone)
    typer.echo(render(payload, fmt=state.effective_output))


@xfr_out.command("set")
def xfr_out_set(
    ctx: typer.Context,
    zone: ZoneArg,
    secondaries: Annotated[
        list[str] | None,
        typer.Option(
            "--secondary",
            help="IP of a secondary nameserver. Repeat for multiple; empty = clear.",
        ),
    ] = None,
    tsigkey: Annotated[
        str | None,
        typer.Option("--tsigkey", help="Preconfigured TSIG key; omit to clear."),
    ] = None,
) -> None:
    """Set outbound xfr. API: POST /api/v2/zones/{zone}/outbound"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = zones_write_api.set_outbound(
            client,
            zone=zone,
            secondaries=secondaries,
            tsigkey=tsigkey,
            dry_run=state.dry_run,
        )
    _render_mutation(result, state)


@xfr_out.command("unset")
def xfr_out_unset(ctx: typer.Context, zone: ZoneArg) -> None:
    """Clear outbound xfr. API: DELETE /api/v2/zones/{zone}/outbound"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = zones_write_api.unset_outbound(
            client,
            zone=zone,
            dry_run=state.dry_run,
        )
    _render_mutation(result, state)

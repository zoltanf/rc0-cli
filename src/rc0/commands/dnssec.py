"""`rc0 dnssec` — DNSSEC sign/unsign/keyrollover/ack-ds and test-env simulate."""

from __future__ import annotations

from typing import Annotated

import typer

from rc0.api import dnssec_write
from rc0.app_state import AppState  # noqa: TC001
from rc0.client.errors import Rc0Error, ValidationError
from rc0.commands._helpers import _client, _render_mutation
from rc0.confirm import confirm_yes_no

app = typer.Typer(name="dnssec", help="Manage DNSSEC for zones.", no_args_is_help=True)

simulate_app = typer.Typer(
    name="simulate",
    help="Simulate DNSSEC events (test environments only).",
    no_args_is_help=True,
)
app.add_typer(simulate_app, name="simulate")

_PROD_URL = "https://my.rcodezero.at"

ZoneArg = Annotated[str, typer.Argument(help="Fully-qualified zone apex, e.g. example.com.")]


# ------------------------------------------------------------------- commands


@app.command("sign")
def sign_cmd(
    ctx: typer.Context,
    zone: ZoneArg,
    ignore_safety_period: Annotated[
        bool,
        typer.Option("--ignore-safety-period", help="Bypass TTL safety period check."),
    ] = False,
    enable_cds_cdnskey: Annotated[
        bool,
        typer.Option("--enable-cds-cdnskey", help="Publish CDS/CDNSKEY records."),
    ] = False,
) -> None:
    """Sign a zone with DNSSEC. API: POST /api/v2/zones/{zone}/sign

    Examples:

      rc0 dnssec sign example.com
      rc0 dnssec sign example.com --enable-cds-cdnskey
      rc0 --dry-run -o json dnssec sign example.com
    """
    state: AppState = ctx.obj
    with _client(state) as client:
        result = dnssec_write.sign_zone(
            client,
            zone=zone,
            ignore_safety_period=ignore_safety_period,
            enable_cds_cdnskey=enable_cds_cdnskey,
            dry_run=state.dry_run,
        )
    _render_mutation(result, state)


@app.command("unsign")
def unsign_cmd(
    ctx: typer.Context,
    zone: ZoneArg,
    force: Annotated[
        bool,
        typer.Option("--force", help="Required — acknowledges that DNSSEC will be removed."),
    ] = False,
) -> None:
    """Remove DNSSEC signing from a zone. API: POST /api/v2/zones/{zone}/unsign

    Requires --force to prevent accidental removal. Prompts for confirmation
    unless -y is passed.

    Examples:

      rc0 dnssec unsign example.com --force
      rc0 dnssec unsign example.com --force -y
      rc0 --dry-run -o json dnssec unsign example.com --force
    """
    state: AppState = ctx.obj
    if not force:
        raise ValidationError(
            "unsign requires --force to prevent accidental removal of DNSSEC.",
            hint="Pass --force to confirm you intend to remove DNSSEC from this zone.",
        )
    if not state.dry_run and not state.yes:
        confirm_yes_no(
            f"Remove DNSSEC signing from {zone}?"
            " This will expose the zone to spoofing until DS records are"
            " cleared at the registrar.",
        )
    with _client(state) as client:
        result = dnssec_write.unsign_zone(client, zone=zone, dry_run=state.dry_run)
    _render_mutation(result, state)


@app.command("keyrollover")
def keyrollover_cmd(ctx: typer.Context, zone: ZoneArg) -> None:
    """Start a KSK rollover. API: POST /api/v2/zones/{zone}/keyrollover"""
    state: AppState = ctx.obj
    if not state.dry_run and not state.yes:
        confirm_yes_no(f"Start KSK rollover for {zone}?")
    with _client(state) as client:
        result = dnssec_write.keyrollover(client, zone=zone, dry_run=state.dry_run)
    _render_mutation(result, state)


@app.command("ack-ds")
def ack_ds_cmd(ctx: typer.Context, zone: ZoneArg) -> None:
    """Acknowledge DS update. API: POST /api/v2/zones/{zone}/dsupdate

    Call after submitting DS records to the parent zone and confirming
    propagation.

    Examples:

      rc0 dnssec ack-ds example.com
      rc0 --dry-run -o json dnssec ack-ds example.com
    """
    state: AppState = ctx.obj
    with _client(state) as client:
        result = dnssec_write.ack_ds(client, zone=zone, dry_run=state.dry_run)
    _render_mutation(result, state)


# ----------------------------------------------------------- simulate sub-group


@simulate_app.callback()
def simulate_callback(ctx: typer.Context) -> None:
    """Test-system only. Blocked when targeting the production API."""
    state: AppState = ctx.obj
    if state.effective_api_url.rstrip("/") == _PROD_URL:
        raise Rc0Error(
            "simulate commands are only available on test environments.",
            hint=(
                "Use --api-url to target a non-production instance"
                " (e.g. https://my-test.rcodezero.at)."
            ),
        )


@simulate_app.command("dsseen")
def simulate_dsseen_cmd(ctx: typer.Context, zone: ZoneArg) -> None:
    """Simulate DS-seen event. API: POST /api/v2/zones/{zone}/simulate/dsseen"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = dnssec_write.simulate_dsseen(client, zone=zone, dry_run=state.dry_run)
    _render_mutation(result, state)


@simulate_app.command("dsremoved")
def simulate_dsremoved_cmd(ctx: typer.Context, zone: ZoneArg) -> None:
    """Simulate DS-removed event. API: POST /api/v2/zones/{zone}/simulate/dsremoved"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = dnssec_write.simulate_dsremoved(client, zone=zone, dry_run=state.dry_run)
    _render_mutation(result, state)

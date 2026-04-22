"""`rc0 settings` — account-level settings (show + Phase 2 setters/unsetters)."""

from __future__ import annotations

from typing import Annotated

import typer

from rc0 import auth as auth_core
from rc0.api import settings as settings_api
from rc0.api import settings_write as settings_write_api
from rc0.app_state import AppState  # noqa: TC001
from rc0.client.dry_run import DryRunResult
from rc0.client.errors import AuthError
from rc0.client.http import Client
from rc0.output import render

app = typer.Typer(
    name="settings",
    help="Manage account-level settings.",
    no_args_is_help=True,
)
secondaries_app = typer.Typer(
    name="secondaries",
    help="Account-wide secondary nameservers.",
    no_args_is_help=True,
)
tsig_in_app = typer.Typer(
    name="tsig-in",
    help="Account-wide inbound TSIG key.",
    no_args_is_help=True,
)
tsig_out_app = typer.Typer(
    name="tsig-out",
    help="Account-wide outbound TSIG key.",
    no_args_is_help=True,
)
app.add_typer(secondaries_app, name="secondaries")
app.add_typer(tsig_in_app, name="tsig-in")
app.add_typer(tsig_out_app, name="tsig-out")


TsigKeyArg = Annotated[str, typer.Argument(help="Preconfigured TSIG key name.")]
IpOpt = Annotated[
    list[str],
    typer.Option(
        "--ip",
        help="Secondary IP (repeatable; at least one required).",
    ),
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


def _render(result: DryRunResult | dict[str, object], state: AppState) -> None:
    payload = result.to_dict() if isinstance(result, DryRunResult) else result
    typer.echo(render(payload, fmt=state.effective_output))


@app.command("show")
def show_cmd(ctx: typer.Context) -> None:
    """Show account settings. API: GET /api/v2/settings"""
    state: AppState = ctx.obj
    with _client(state) as client:
        s = settings_api.show_settings(client)
    typer.echo(render(s.model_dump(exclude_none=True), fmt=state.effective_output))


@secondaries_app.command("set")
def secondaries_set(ctx: typer.Context, ips: IpOpt) -> None:
    """Set account-wide secondaries. API: PUT /api/v2/settings/secondaries"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = settings_write_api.set_secondaries(
            client,
            ips=ips,
            dry_run=state.dry_run,
        )
    _render(result, state)


@secondaries_app.command("unset")
def secondaries_unset(ctx: typer.Context) -> None:
    """Clear account-wide secondaries. API: DELETE /api/v2/settings/secondaries"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = settings_write_api.unset_secondaries(client, dry_run=state.dry_run)
    _render(result, state)


@tsig_in_app.command("set")
def tsig_in_set(ctx: typer.Context, tsigkey: TsigKeyArg) -> None:
    """Set account-wide inbound TSIG key. API: PUT /api/v2/settings/tsig/in"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = settings_write_api.set_tsig_in(
            client,
            tsigkey=tsigkey,
            dry_run=state.dry_run,
        )
    _render(result, state)


@tsig_in_app.command("unset")
def tsig_in_unset(ctx: typer.Context) -> None:
    """Clear account-wide inbound TSIG key. API: DELETE /api/v2/settings/tsig/in"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = settings_write_api.unset_tsig_in(client, dry_run=state.dry_run)
    _render(result, state)


@tsig_out_app.command("set")
def tsig_out_set(ctx: typer.Context, tsigkey: TsigKeyArg) -> None:
    """Set account-wide outbound TSIG key. API: PUT /api/v2/settings/tsig/out"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = settings_write_api.set_tsig_out(
            client,
            tsigkey=tsigkey,
            dry_run=state.dry_run,
        )
    _render(result, state)


@tsig_out_app.command("unset")
def tsig_out_unset(ctx: typer.Context) -> None:
    """Clear account-wide outbound TSIG key. API: DELETE /api/v2/settings/tsig/out"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = settings_write_api.unset_tsig_out(client, dry_run=state.dry_run)
    _render(result, state)

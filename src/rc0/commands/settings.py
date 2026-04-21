"""`rc0 settings` — account-level settings (Phase 1 read-only surface)."""

from __future__ import annotations

import typer

from rc0 import auth as auth_core
from rc0.api import settings as settings_api
from rc0.app_state import AppState  # noqa: TC001
from rc0.client.errors import AuthError
from rc0.client.http import Client
from rc0.output import render

app = typer.Typer(
    name="settings",
    help="Manage account-level settings.",
    no_args_is_help=True,
)


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


@app.command("show")
def show_cmd(ctx: typer.Context) -> None:
    """Show account settings. API: GET /api/v2/settings"""
    state: AppState = ctx.obj
    with _client(state) as client:
        s = settings_api.show_settings(client)
    typer.echo(render(s.model_dump(exclude_none=True), fmt=state.effective_output))

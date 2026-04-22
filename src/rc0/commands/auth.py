"""`rc0 auth` — login / logout / status / whoami."""

from __future__ import annotations

import getpass
from typing import Annotated

import typer

from rc0 import auth as auth_core
from rc0.app_state import AppState  # noqa: TC001 — needed for Typer context type
from rc0.client.errors import AuthError, ConfigError
from rc0.client.http import Client
from rc0.output import render

app = typer.Typer(
    name="auth",
    help="Authenticate with the RcodeZero API.",
    no_args_is_help=True,
)


@app.command("login")
def login(
    ctx: typer.Context,
    token: Annotated[
        str | None,
        typer.Option(
            "--token-value",
            help="Provide the token non-interactively (useful for scripts).",
        ),
    ] = None,
    use_file: Annotated[
        bool,
        typer.Option(
            "--file",
            help="Skip keyring; write to the 0600 credentials file instead.",
        ),
    ] = False,
) -> None:
    """Prompt for an API token, validate it, and store it.

    Examples:

      rc0 auth login
      rc0 auth login --token "$RC0_API_TOKEN"
      rc0 --profile staging auth login
    """
    state: AppState = ctx.obj
    raw_token = token or getpass.getpass("API token: ")
    if not raw_token:
        raise ConfigError("No token provided.")

    _validate_token(state.effective_api_url, raw_token, timeout=state.effective_timeout)

    record = auth_core.store_token(
        state.profile_name,
        raw_token,
        prefer_keyring=not use_file,
    )
    payload = {
        "profile": record.profile,
        "backend": record.backend,
        "token_tail": record.tail,
        "message": f"Authenticated. Token stored in {record.backend}.",
    }
    typer.echo(render(payload, fmt=state.effective_output))


@app.command("logout")
def logout(ctx: typer.Context) -> None:
    """Remove the stored token for the active profile.

    Examples:

      rc0 auth logout
      rc0 --profile staging auth logout
    """
    state: AppState = ctx.obj
    removed = auth_core.delete_token(state.profile_name)
    payload = {
        "profile": state.profile_name,
        "removed": removed,
        "message": (
            f"Removed stored token for profile {state.profile_name!r}."
            if removed
            else f"No stored token for profile {state.profile_name!r}."
        ),
    }
    typer.echo(render(payload, fmt=state.effective_output))


@app.command("status")
def status(ctx: typer.Context) -> None:
    """Show where the active token is stored, without revealing its value.

    Examples:

      rc0 auth status
      rc0 --profile staging auth status
    """
    state: AppState = ctx.obj
    record = auth_core.load_token(state.profile_name)
    if record is None:
        payload = {
            "profile": state.profile_name,
            "authenticated": False,
            "message": f"Not authenticated on profile {state.profile_name!r}.",
        }
    else:
        payload = {
            "profile": record.profile,
            "authenticated": True,
            "backend": record.backend,
            "token_tail": record.tail,
            "message": (
                f"Authenticated as profile {record.profile!r} using token ending in {record.tail} "
                f"(backend: {record.backend})."
            ),
        }
    typer.echo(render(payload, fmt=state.effective_output))


@app.command("whoami")
def whoami(ctx: typer.Context) -> None:
    """Alias for :func:`status`."""
    status(ctx)


# ------------------------------------------------------------------- helpers


def _validate_token(api_url: str, token: str, *, timeout: float) -> None:
    """Hit ``GET /api/v2/zones?page_size=1`` to confirm the token is valid."""
    with Client(api_url=api_url, token=token, timeout=timeout) as client:
        try:
            client.get("/api/v2/zones", params={"page_size": 1})
        except AuthError as exc:
            raise AuthError(
                "Token rejected by the RcodeZero API.",
                hint="Double-check the token and that the profile's --api-url is correct.",
            ) from exc

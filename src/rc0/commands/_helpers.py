"""Shared helpers used by every command module."""

from __future__ import annotations

import typer

from rc0 import auth as auth_core
from rc0.app_state import AppState  # noqa: TC001
from rc0.client.dry_run import DryRunResult
from rc0.client.errors import AuthError, ValidationError
from rc0.client.http import Client
from rc0.output import render


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


def _render_mutation(result: DryRunResult | dict[str, object], state: AppState) -> None:
    payload = result.to_dict() if isinstance(result, DryRunResult) else result
    typer.echo(render(payload, fmt=state.effective_output))


def _validate_pagination(fetch_all: bool, page: int | None) -> None:
    if fetch_all and page is not None:
        raise ValidationError(
            "--page cannot be combined with --all.",
            hint="Use --all to iterate every page, or --page/--page-size to select one page.",
        )

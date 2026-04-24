"""Shared helpers used by every command module."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from rc0 import auth as auth_core
from rc0.app_state import AppState  # noqa: TC001
from rc0.client.dry_run import DryRunResult
from rc0.client.errors import AuthError, ValidationError
from rc0.client.http import Client
from rc0.output import render

if TYPE_CHECKING:
    from collections.abc import Sized

    from rc0.client.pagination import PageInfo


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
            hint="Omit both to fetch every row, or use --page/--page-size for a single page.",
        )


def _warn_if_truncated(state: AppState, rows: Sized, info: PageInfo) -> None:
    """Emit a stderr warning when an explicit --page request left rows behind.

    Silent when ``state.quiet`` is set, when the response clearly covered
    everything (envelope with ``current_page == last_page``, or a bare array
    that returned fewer than ``per_page`` rows).
    """
    if state.quiet:
        return
    if info.is_envelope:
        if info.last_page is None or info.current_page >= info.last_page:
            return
        total_note = (
            f"{len(rows)} of {info.total} rows" if info.total is not None else f"{len(rows)} rows"
        )
        message = (
            f"warning: showing page {info.current_page} of {info.last_page} "
            f"({total_note}). Omit --page to fetch every row."
        )
    else:
        if len(rows) < info.per_page:
            return
        message = (
            f"warning: page {info.current_page} returned a full page ({len(rows)} rows); "
            "more rows may exist. Omit --page to fetch every row."
        )
    typer.secho(message, err=True, fg=typer.colors.YELLOW)

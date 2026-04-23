"""`rc0 tsig` — list / show + deprecated list-out + write commands."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

import typer

from rc0.api import tsig as tsig_api
from rc0.api import tsig_write as tsig_write_api
from rc0.app_state import AppState  # noqa: TC001
from rc0.commands._deprecated import deprecated_warn
from rc0.commands._helpers import _client, _render_mutation, _validate_pagination
from rc0.confirm import confirm_yes_no
from rc0.output import render

app = typer.Typer(name="tsig", help="Manage TSIG keys.", no_args_is_help=True)

NameArg = Annotated[str, typer.Argument(help="TSIG key name.")]
PageOpt = Annotated[
    int | None,
    typer.Option("--page", min=1, help="1-indexed page number (incompatible with --all)."),
]
PageSizeOpt = Annotated[
    int | None,
    typer.Option("--page-size", min=1, max=1000, help="Rows per page (default 50)."),
]


@app.command("list")
def list_cmd(
    ctx: typer.Context,
    page: PageOpt = None,
    page_size: PageSizeOpt = None,
    fetch_all: Annotated[bool, typer.Option("--all", help="Auto-paginate every row.")] = False,
) -> None:
    """List TSIG keys. API: GET /api/v2/tsig

    Examples:

      rc0 tsig list
      rc0 -o json tsig list
    """
    state: AppState = ctx.obj
    _validate_pagination(fetch_all, page)
    with _client(state) as client:
        keys = tsig_api.list_tsig(
            client,
            page=page,
            page_size=page_size,
            fetch_all=fetch_all,
        )
    typer.echo(
        render(
            [k.model_dump(exclude_none=True) for k in keys],
            fmt=state.effective_output,
            columns=["name", "algorithm", "id"],
        ),
    )


@app.command("show")
def show_cmd(ctx: typer.Context, name: NameArg) -> None:
    """Show one TSIG key. API: GET /api/v2/tsig/{keyname}"""
    state: AppState = ctx.obj
    with _client(state) as client:
        k = tsig_api.show_tsig(client, name)
    typer.echo(render(k.model_dump(exclude_none=True), fmt=state.effective_output))


@app.command("list-out", hidden=True)
def list_out_cmd(ctx: typer.Context) -> None:
    """[DEPRECATED] Show the legacy outgoing TSIG key. API: GET /api/v2/tsig/out"""
    deprecated_warn("rc0 tsig list-out")
    state: AppState = ctx.obj
    with _client(state) as client:
        payload = tsig_api.list_tsig_out_deprecated(client)
    typer.echo(render(payload, fmt=state.effective_output))


# ---------------------------------------------------------- Phase 2 mutations


class AlgorithmChoice(StrEnum):
    """Typer-friendly enum of the RcodeZero-supported TSIG algorithms."""

    hmac_md5 = "hmac-md5"
    hmac_sha1 = "hmac-sha1"
    hmac_sha224 = "hmac-sha224"
    hmac_sha256 = "hmac-sha256"
    hmac_sha384 = "hmac-sha384"
    hmac_sha512 = "hmac-sha512"


AlgorithmOpt = Annotated[
    AlgorithmChoice,
    typer.Option("--algorithm", help="TSIG algorithm.", case_sensitive=False),
]
SecretOpt = Annotated[
    str,
    typer.Option("--secret", help="Base64-encoded shared secret."),
]


@app.command("add")
def add_cmd(
    ctx: typer.Context,
    name: NameArg,
    algorithm: AlgorithmOpt,
    secret: SecretOpt,
) -> None:
    """Add a TSIG key. API: POST /api/v2/tsig

    Examples:

      rc0 tsig add mykey --algorithm hmac-sha256 --secret base64secret==
      rc0 --dry-run -o json tsig add mykey --algorithm hmac-sha256 --secret base64secret==
    """
    state: AppState = ctx.obj
    with _client(state) as client:
        result = tsig_write_api.add_tsig(
            client,
            name=name,
            algorithm=algorithm.value,
            secret=secret,
            dry_run=state.dry_run,
        )
    _render_mutation(result, state)


@app.command("update")
def update_cmd(
    ctx: typer.Context,
    name: NameArg,
    algorithm: AlgorithmOpt,
    secret: SecretOpt,
) -> None:
    """Update a TSIG key. API: PUT /api/v2/tsig/{keyname}"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = tsig_write_api.update_tsig(
            client,
            name=name,
            algorithm=algorithm.value,
            secret=secret,
            dry_run=state.dry_run,
        )
    _render_mutation(result, state)


@app.command("delete")
def delete_cmd(ctx: typer.Context, name: NameArg) -> None:
    """Delete a TSIG key. API: DELETE /api/v2/tsig/{keyname}

    Prompts for confirmation unless -y is passed.

    Examples:

      rc0 tsig delete mykey
      rc0 tsig delete mykey -y
      rc0 --dry-run -o json tsig delete mykey
    """
    state: AppState = ctx.obj
    if not state.dry_run and not state.yes:
        confirm_yes_no(f"Would delete TSIG key {name}.")
    with _client(state) as client:
        result = tsig_write_api.delete_tsig(client, name=name, dry_run=state.dry_run)
    _render_mutation(result, state)

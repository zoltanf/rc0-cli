"""`rc0 record` — list / export (Phase 1 read-only surface)."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from rc0 import auth as auth_core
from rc0.api import rrsets as rrsets_api
from rc0.api import rrsets_write as rrsets_write_api
from rc0.app_state import AppState  # noqa: TC001
from rc0.client.dry_run import DryRunResult
from rc0.client.errors import AuthError, ValidationError
from rc0.client.http import Client
from rc0.output import OutputFormat, render
from rc0.output.bind import render_rrsets
from rc0.rrsets import parse as rrsets_parse
from rc0.validation import rrsets as rrsets_validate

if TYPE_CHECKING:
    from collections.abc import Callable

app = typer.Typer(name="record", help="Manage RRsets.", no_args_is_help=True)

ZoneArg = Annotated[str, typer.Argument(help="Zone apex, e.g. example.com.")]


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
    zone: ZoneArg,
    name: Annotated[
        str | None,
        typer.Option("--name", help="Filter by RR name."),
    ] = None,
    type_: Annotated[
        str | None,
        typer.Option("--type", help="Filter by RR type."),
    ] = None,
    page: Annotated[
        int | None,
        typer.Option("--page", min=1, help="1-indexed page number (incompatible with --all)."),
    ] = None,
    page_size: Annotated[
        int | None,
        typer.Option("--page-size", min=1, max=1000, help="Rows per page (default 50)."),
    ] = None,
    fetch_all: Annotated[
        bool,
        typer.Option("--all", help="Auto-paginate every row."),
    ] = False,
) -> None:
    """List RRsets. API: GET /api/v2/zones/{zone}/rrsets"""
    state: AppState = ctx.obj
    if fetch_all and page is not None:
        raise ValidationError(
            "--page cannot be combined with --all.",
            hint="Use --all to iterate every page, or --page/--page-size to select one page.",
        )
    with _client(state) as client:
        rows = rrsets_api.list_rrsets(
            client,
            zone,
            name=name,
            type=type_,
            page=page,
            page_size=page_size,
            fetch_all=fetch_all,
        )
    typer.echo(
        render(
            [r.model_dump(exclude_none=True) for r in rows],
            fmt=state.effective_output,
            columns=["name", "type", "ttl", "records"],
        ),
    )


@app.command("export")
def export_cmd(
    ctx: typer.Context,
    zone: ZoneArg,
    fmt: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format: bind (default), json, or yaml.",
            case_sensitive=False,
        ),
    ] = "bind",
) -> None:
    """Export every RRset in a zone. API: GET /api/v2/zones/{zone}/rrsets"""
    state: AppState = ctx.obj
    fmt_lower = fmt.lower()
    if fmt_lower not in {"bind", "json", "yaml"}:
        raise ValidationError(
            f"Unsupported --format {fmt!r}.",
            hint="Valid formats: bind, json, yaml.",
        )
    with _client(state) as client:
        rows = rrsets_api.list_rrsets(client, zone, fetch_all=True)
    payload = [r.model_dump(exclude_none=True) for r in rows]
    if fmt_lower == "bind":
        typer.echo(render_rrsets(zone=zone, rrsets=payload))
    else:
        typer.echo(render(payload, fmt=OutputFormat(fmt_lower)))


# ---------------------------------------------------------- Phase 3 mutations


class RecordType(StrEnum):
    """A permissive enum — Typer only uses it for case-insensitive parsing.

    We don't fence on type here: the API validates the RR type, and adding a
    whitelist would block valid new types (SVCB, HTTPS, …) the moment they ship.
    """

    A = "A"
    AAAA = "AAAA"
    CNAME = "CNAME"
    MX = "MX"
    TXT = "TXT"
    NS = "NS"
    SRV = "SRV"
    CAA = "CAA"
    PTR = "PTR"
    SOA = "SOA"


NameOpt = Annotated[
    str,
    typer.Option(
        "--name",
        help="Record name. Relative to the zone or absolute (with trailing dot).",
    ),
]
TypeOpt = Annotated[
    str,
    typer.Option(
        "--type",
        help="RR type, e.g. A, AAAA, MX, CNAME, TXT. Case-insensitive.",
    ),
]
TtlOpt = Annotated[
    int,
    typer.Option("--ttl", min=1, help="TTL in seconds (must be ≥ 60, the provider floor)."),
]
ContentOpt = Annotated[
    list[str] | None,
    typer.Option(
        "--content",
        help="Record content. Repeat to aggregate into one RRset (A/AAAA/TXT/…); "
        "for MX, use `--content '10 mail.example.com.'`.",
    ),
]
DisabledOpt = Annotated[
    bool,
    typer.Option(
        "--disabled/--enabled",
        help="Store but hide the record (API disabled=true). Default: enabled.",
    ),
]
FromFileOpt = Annotated[
    Path | None,
    typer.Option(
        "--from-file",
        help="Path to a JSON/YAML file mirroring the PATCH body (list of rrset changes).",
        exists=False,  # we raise our own ValidationError to stay on exit 7
    ),
]
ZoneFileOpt = Annotated[
    Path | None,
    typer.Option(
        "--zone-file",
        help="Path to a BIND zone file (only for `record replace-all`).",
    ),
]


def _render_mutation(
    result: DryRunResult | dict[str, object],
    state: AppState,
) -> None:
    payload = result.to_dict() if isinstance(result, DryRunResult) else result
    typer.echo(render(payload, fmt=state.effective_output))


def _warn(state: AppState) -> Callable[[str], None]:
    """Build a stderr warner bound to this invocation's verbosity."""

    def _emit(line: str) -> None:
        if state.verbose >= 1:
            typer.secho(line, err=True)

    return _emit


@app.command("add")
def add_cmd(
    ctx: typer.Context,
    zone: ZoneArg,
    name: NameOpt,
    type_: TypeOpt,
    contents: ContentOpt = None,
    ttl: TtlOpt = 3600,
    disabled: DisabledOpt = False,
) -> None:
    """Add a single RRset. API: PATCH /api/v2/zones/{zone}/rrsets"""
    state: AppState = ctx.obj
    change = rrsets_parse.from_flags(
        name=name,
        type_=type_,
        ttl=ttl,
        contents=list(contents or []),
        disabled=disabled,
        changetype="add",
        zone=zone,
        verbose=state.verbose,
        warn=_warn(state),
    )
    rrsets_validate.validate_changes([change])
    with _client(state) as client:
        result = rrsets_write_api.patch_rrsets(
            client,
            zone=zone,
            changes=[change],
            dry_run=state.dry_run,
            summary=f"Would add {change.type} rrset {change.name} "
            f"({len(change.records)} record(s)).",
            side_effects=["creates_rrset"],
        )
    _render_mutation(result, state)


@app.command("update")
def update_cmd(
    ctx: typer.Context,
    zone: ZoneArg,
    name: NameOpt,
    type_: TypeOpt,
    contents: ContentOpt = None,
    ttl: TtlOpt = 3600,
    disabled: DisabledOpt = False,
) -> None:
    """Replace an RRset's records. API: PATCH /api/v2/zones/{zone}/rrsets"""
    state: AppState = ctx.obj
    change = rrsets_parse.from_flags(
        name=name,
        type_=type_,
        ttl=ttl,
        contents=list(contents or []),
        disabled=disabled,
        changetype="update",
        zone=zone,
        verbose=state.verbose,
        warn=_warn(state),
    )
    rrsets_validate.validate_changes([change])
    with _client(state) as client:
        result = rrsets_write_api.patch_rrsets(
            client,
            zone=zone,
            changes=[change],
            dry_run=state.dry_run,
            summary=f"Would replace records on {change.type} rrset {change.name} "
            f"(to {len(change.records)} record(s)).",
            side_effects=["updates_rrset"],
        )
    _render_mutation(result, state)

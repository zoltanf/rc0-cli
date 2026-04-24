"""`rc0 record` — list / export (Phase 1 read-only surface)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer
from pydantic import ValidationError as PydanticValidationError

from rc0.api import rrsets as rrsets_api
from rc0.api import rrsets_write as rrsets_write_api
from rc0.app_state import AppState  # noqa: TC001
from rc0.client.errors import ValidationError
from rc0.commands._helpers import (
    _client,
    _render_mutation,
    _validate_pagination,
    _warn_if_truncated,
)
from rc0.confirm import confirm_typed, confirm_yes_no
from rc0.output import OutputFormat, render
from rc0.output.bind import render_rrsets
from rc0.rrsets import parse as rrsets_parse
from rc0.validation import rrsets as rrsets_validate

if TYPE_CHECKING:
    from collections.abc import Callable

    from rc0.models.rrset_write import RRsetInput

app = typer.Typer(name="record", help="Manage RRsets.", no_args_is_help=True)

ZoneArg = Annotated[str, typer.Argument(help="Zone apex, e.g. example.com.")]


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
        typer.Option(
            "--page",
            min=1,
            help="Fetch only this 1-indexed page. Omit to fetch every row.",
        ),
    ] = None,
    page_size: Annotated[
        int | None,
        typer.Option(
            "--page-size",
            min=1,
            max=1000,
            help="Rows per HTTP request (default 50).",
        ),
    ] = None,
    fetch_all: Annotated[
        bool,
        typer.Option(
            "--all",
            help="[kept for compatibility] fetching every row is now the default.",
        ),
    ] = False,
) -> None:
    """List RRsets. API: GET /api/v2/zones/{zone}/rrsets

    Fetches every RRset by default. Use ``--page N`` to retrieve a single
    page (a stderr warning fires if more rows exist).

    Examples:

      rc0 record list example.com
      rc0 record list example.com --name www --type A
      rc0 record list example.com --page 2 --page-size 25
    """
    state: AppState = ctx.obj
    _validate_pagination(fetch_all, page)
    with _client(state) as client:
        if page is not None:
            rows, info = rrsets_api.list_rrsets_page(
                client,
                zone,
                name=name,
                type=type_,
                page=page,
                page_size=page_size,
            )
        else:
            rows = rrsets_api.list_rrsets(
                client,
                zone,
                name=name,
                type=type_,
                page_size=page_size,
                fetch_all=True,
            )
            info = None
    typer.echo(
        render(
            [r.model_dump(exclude_none=True) for r in rows],
            fmt=state.effective_output,
            columns=["name", "type", "ttl", "records"],
        ),
    )
    if info is not None:
        _warn_if_truncated(state, rows, info)


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
    """Add a single RRset. API: PATCH /api/v2/zones/{zone}/rrsets

    Examples:

      rc0 record add example.com --name www --type A --content 10.0.0.1
      rc0 record add example.com --name mail --type MX --content '10 mail.example.com.'
      rc0 record add example.com --name www --type A --content 10.0.0.1 --content 10.0.0.2
      rc0 --dry-run -o json record add example.com --name www --type A --content 10.0.0.1
    """
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
    """Replace an RRset's records. API: PATCH /api/v2/zones/{zone}/rrsets

    Examples:

      rc0 record update example.com --name www --type A --content 10.0.0.1 --ttl 300
      rc0 record update example.com --name www --type A --content 10.0.0.1 --dry-run
    """
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


@app.command("delete")
def delete_cmd(
    ctx: typer.Context,
    zone: ZoneArg,
    name: NameOpt,
    type_: TypeOpt,
    ttl: TtlOpt = 3600,
) -> None:
    """Delete an RRset. API: PATCH /api/v2/zones/{zone}/rrsets (changetype=delete)

    Prompts for confirmation unless -y is passed.

    Examples:

      rc0 record delete example.com --name www --type A
      rc0 record delete example.com --name www --type A -y
      rc0 --dry-run -o json record delete example.com --name www --type A
    """
    state: AppState = ctx.obj
    change = rrsets_parse.from_flags(
        name=name,
        type_=type_,
        ttl=ttl,
        contents=[],
        disabled=False,
        changetype="delete",
        zone=zone,
        verbose=state.verbose,
        warn=_warn(state),
    )
    rrsets_validate.validate_changes([change])
    if not state.dry_run and not state.yes:
        confirm_yes_no(
            f"Would delete {change.type} rrset {change.name} from zone {zone}.",
        )
    with _client(state) as client:
        result = rrsets_write_api.patch_rrsets(
            client,
            zone=zone,
            changes=[change],
            dry_run=state.dry_run,
            summary=f"Would delete {change.type} rrset {change.name}.",
            side_effects=["deletes_rrset"],
        )
    _render_mutation(result, state)


@app.command("apply")
def apply_cmd(
    ctx: typer.Context,
    zone: ZoneArg,
    from_file: FromFileOpt = None,
) -> None:
    """Apply a batch of rrset changes from a JSON/YAML file.

    API: PATCH /api/v2/zones/{zone}/rrsets

    The file format mirrors the API PATCH body exactly (a list of rrset change
    objects, each with ``changetype`` set to ``add``, ``update`` or ``delete``).
    See `rc0 help rrset-format` for the full schema.
    """
    state: AppState = ctx.obj
    if from_file is None:
        raise ValidationError(
            "`record apply` requires --from-file.",
            hint="Pass a JSON/YAML file with the rrset changes; see `rc0 help rrset-format`.",
        )
    changes = rrsets_parse.from_file(
        from_file,
        zone=zone,
        verbose=state.verbose,
        warn=_warn(state),
    )
    rrsets_validate.validate_changes(changes)
    if not state.dry_run and not state.yes:
        confirm_typed(
            zone,
            summary=(
                f"Would apply {len(changes)} rrset change(s) to {zone} (mixed add/update/delete)."
            ),
        )
    with _client(state) as client:
        result = rrsets_write_api.patch_rrsets(
            client,
            zone=zone,
            changes=changes,
            dry_run=state.dry_run,
            summary=f"Would apply {len(changes)} rrset change(s) to {zone}.",
            side_effects=["applies_rrset_batch"],
        )
    _render_mutation(result, state)


@app.command("replace-all")
def replace_all_cmd(
    ctx: typer.Context,
    zone: ZoneArg,
    from_file: FromFileOpt = None,
    zone_file: ZoneFileOpt = None,
) -> None:
    """Full zone replacement (zone-transfer semantics).

    API: PUT /api/v2/zones/{zone}/rrsets

    Accepts exactly one of:
      --from-file  JSON/YAML file of rrsets (no `changetype` — each row is the
                   desired final state at that name/type).
      --zone-file  BIND zone file; parsed via dnspython.

    Replaces every rrset in the zone. This is destructive: anything not in the
    input disappears. Prompts for typed-zone confirmation by default.
    """
    state: AppState = ctx.obj
    if (from_file is None) == (zone_file is None):
        raise ValidationError(
            "`record replace-all` needs exactly one of --from-file or --zone-file.",
            hint="JSON/YAML for API-shape input; BIND for zone-file input.",
        )
    if from_file is not None:
        # The PATCH-shape file parser would fail on rows without changetype; we
        # need the PUT shape. Load rows directly and build RRsetInput.
        rrsets = _load_rrsets_from_file(
            from_file,
            zone=zone,
            verbose=state.verbose,
            warn=_warn(state),
        )
    else:
        assert zone_file is not None
        rrsets = rrsets_parse.from_zonefile(zone_file, zone=zone)
    rrsets_validate.validate_replacement(rrsets)
    if not state.dry_run and not state.yes:
        confirm_typed(
            zone,
            summary=(
                f"Would REPLACE every rrset in {zone} with {len(rrsets)} rrset(s). "
                "This discards anything not in the input."
            ),
        )
    with _client(state) as client:
        result = rrsets_write_api.put_rrsets(
            client,
            zone=zone,
            rrsets=rrsets,
            dry_run=state.dry_run,
            summary=f"Would replace every rrset in {zone} with {len(rrsets)} rrset(s).",
        )
    _render_mutation(result, state)


@app.command("clear")
def clear_cmd(ctx: typer.Context, zone: ZoneArg) -> None:
    """Delete every non-apex RRset in a zone.

    API: DELETE /api/v2/zones/{zone}/rrsets

    SOA and NS rrsets at the apex survive; everything else is wiped. Prompts
    for typed-zone confirmation by default.
    """
    state: AppState = ctx.obj
    if not state.dry_run and not state.yes:
        confirm_typed(
            zone,
            summary=f"Would clear every non-apex rrset from {zone}. This cannot be undone.",
        )
    with _client(state) as client:
        result = rrsets_write_api.clear_rrsets(
            client,
            zone=zone,
            dry_run=state.dry_run,
        )
    _render_mutation(result, state)


def _load_rrsets_from_file(
    path: Path,
    *,
    zone: str,
    verbose: int,
    warn: Callable[[str], None],
) -> list[RRsetInput]:
    """Load a JSON/YAML file as RRsetInput[] (PUT body, no `changetype`)."""
    import yaml as _yaml

    from rc0.models.rrset_write import RRsetInput

    suffix = path.suffix.lower()
    if suffix not in {".json", ".yaml", ".yml"}:
        raise ValidationError(
            f"Unsupported --from-file extension {suffix!r}.",
            hint="Use .json, .yaml, or .yml.",
        )
    text = path.read_text(encoding="utf-8")
    raw = json.loads(text) if suffix == ".json" else _yaml.safe_load(text)
    if not isinstance(raw, list):
        raise ValidationError(
            f"{path} must be a list of rrset objects.",
            hint="See `rc0 help rrset-format`.",
        )
    out: list[RRsetInput] = []
    for i, row in enumerate(raw):
        if not isinstance(row, dict):
            raise ValidationError(
                f"Item {i} in {path} must be an object.",
            )
        raw_name = row.get("name", "")
        if not isinstance(raw_name, str):
            raise ValidationError(f"Item {i} in {path} has no string `name`.")
        qualified, rewritten = rrsets_validate.qualify_name(raw_name, zone=zone)
        if rewritten and verbose >= 1:
            warn(f"auto-qualified name {raw_name!r} → {qualified!r}")
        try:
            out.append(RRsetInput.model_validate({**row, "name": qualified}))
        except PydanticValidationError as exc:
            raise ValidationError(
                f"Item {i} in {path} failed validation: "
                + "; ".join(
                    f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
                ),
                hint="`record replace-all --from-file` expects rows without "
                "`changetype` — each row is the desired final state.",
            ) from exc
    return out

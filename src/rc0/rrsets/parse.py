"""Parsers that turn user input into :class:`RRsetChange`/:class:`RRsetInput`.

Every parser:

* Qualifies relative names via :func:`rc0.validation.rrsets.qualify_name`.
* Emits a one-line warning per auto-qualified name to ``warn`` when
  ``verbose >= 1`` — matches mission-plan §12 ("auto-fix, warn in verbose").
* Produces already-typed Pydantic models; the caller runs the batch validators
  (PATCH/PUT size, CNAME exclusivity) after aggregation.
"""

from __future__ import annotations

import json
from pathlib import Path  # noqa: TC003
from typing import TYPE_CHECKING

import yaml
from pydantic import ValidationError as PydanticValidationError

from rc0.client.errors import ValidationError
from rc0.models.rrset_write import (
    ChangeType,
    RecordInput,
    RRsetChange,
)
from rc0.validation.rrsets import qualify_name

if TYPE_CHECKING:
    from collections.abc import Callable


def _maybe_warn(
    *,
    raw: str,
    qualified: str,
    rewritten: bool,
    verbose: int,
    warn: Callable[[str], None],
) -> None:
    if rewritten and verbose >= 1:
        warn(f"auto-qualified name {raw!r} → {qualified!r}")


def from_flags(
    *,
    name: str,
    type_: str,
    ttl: int,
    contents: list[str],
    disabled: bool,
    changetype: ChangeType,
    zone: str,
    verbose: int,
    warn: Callable[[str], None],
) -> RRsetChange:
    """Build a single-row PATCH change from CLI flag inputs."""
    qualified, rewritten = qualify_name(name, zone=zone)
    _maybe_warn(
        raw=name,
        qualified=qualified,
        rewritten=rewritten,
        verbose=verbose,
        warn=warn,
    )
    if changetype != "delete" and not contents:
        raise ValidationError(
            f"`record {changetype}` requires at least one --content value.",
            hint="Pass one --content per record, or use `record delete` to drop the whole RRset.",
        )
    return RRsetChange(
        name=qualified,
        type=type_.upper(),
        ttl=ttl,
        changetype=changetype,
        records=[RecordInput(content=c, disabled=disabled) for c in contents],
    )


_SUPPORTED_SUFFIXES: frozenset[str] = frozenset({".json", ".yaml", ".yml"})


def _load_list_of_dicts(path: Path) -> list[dict[str, object]]:
    suffix = path.suffix.lower()
    if suffix not in _SUPPORTED_SUFFIXES:
        raise ValidationError(
            f"Unsupported file extension {suffix!r} for --from-file.",
            hint="Use .json, .yaml, or .yml.",
        )
    raw_text = path.read_text(encoding="utf-8")
    parsed: object
    if suffix == ".json":
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise ValidationError(
                f"Invalid JSON in {path}: {exc.msg} (line {exc.lineno}).",
                hint="Check for trailing commas or mismatched brackets.",
            ) from exc
    else:
        try:
            parsed = yaml.safe_load(raw_text)
        except yaml.YAMLError as exc:
            raise ValidationError(
                f"Invalid YAML in {path}: {exc}.",
                hint="Run a YAML linter on the file.",
            ) from exc
    if not isinstance(parsed, list):
        raise ValidationError(
            f"{path} must be a list of rrset change objects, got {type(parsed).__name__}.",
            hint="See `rc0 help rrset-format` for the expected shape.",
        )
    rows: list[dict[str, object]] = []
    for i, item in enumerate(parsed):
        if not isinstance(item, dict):
            raise ValidationError(
                f"Item {i} in {path} must be an object, got {type(item).__name__}.",
            )
        rows.append(item)
    return rows


def from_file(
    path: Path,
    *,
    zone: str,
    verbose: int,
    warn: Callable[[str], None],
) -> list[RRsetChange]:
    """Parse a JSON/YAML file into a list of :class:`RRsetChange`.

    File shape (one list item per rrset, mirrors the API PATCH body):

    .. code-block:: yaml

       - name: www.example.com.
         type: A
         ttl: 3600
         changetype: add
         records:
           - content: 10.0.0.1
    """
    rows = _load_list_of_dicts(path)
    changes: list[RRsetChange] = []
    for i, row in enumerate(rows):
        raw_name = row.get("name")
        if not isinstance(raw_name, str):
            raise ValidationError(
                f"Item {i} in {path} is missing a string `name`.",
            )
        qualified, rewritten = qualify_name(raw_name, zone=zone)
        _maybe_warn(
            raw=raw_name,
            qualified=qualified,
            rewritten=rewritten,
            verbose=verbose,
            warn=warn,
        )
        try:
            change = RRsetChange.model_validate({**row, "name": qualified})
        except PydanticValidationError as exc:
            raise ValidationError(
                f"Item {i} in {path} failed validation: "
                + "; ".join(
                    f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
                ),
                hint="See `rc0 help rrset-format` for the expected shape.",
            ) from exc
        changes.append(change)
    return changes

"""Parsers that turn user input into :class:`RRsetChange`/:class:`RRsetInput`.

Every parser:

* Qualifies relative names via :func:`rc0.validation.rrsets.qualify_name`.
* Emits a one-line warning per auto-qualified name to ``warn`` when
  ``verbose >= 1`` — matches mission-plan §12 ("auto-fix, warn in verbose").
* Produces already-typed Pydantic models; the caller runs the batch validators
  (PATCH/PUT size, CNAME exclusivity) after aggregation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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

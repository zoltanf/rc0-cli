"""Client-side validators for /rrsets mutations (mission plan §12).

All public functions raise :class:`rc0.client.errors.ValidationError` on
failure, which maps to exit code 7 (§11). The messages carry an actionable
``hint``.

The validators are pure: no I/O, no HTTP. This lets the CLI fail fast before
spending a network round-trip, and keeps the logic trivially unit-testable.
"""

from __future__ import annotations

import ipaddress
import re
from typing import TYPE_CHECKING

from rc0.client.errors import ValidationError
from rc0.models.rrset_write import (
    CNAME_CONFLICT_TYPES,
    MIN_TTL,
    PATCH_MAX_RRSETS,
    PUT_MAX_RRSETS,
    RRsetChange,
    RRsetInput,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

_MX_PATTERN = re.compile(r"^\s*(\d+)\s+(\S.*?)\s*$")


def qualify_name(raw: str, *, zone: str) -> tuple[str, bool]:
    """Return ``(fqdn, was_rewritten)`` for a user-supplied record name.

    Rules (mission plan §12):
    * ``@`` → zone apex.
    * Name without trailing dot that does not end in the zone → append ``.<zone>.``.
    * Name without trailing dot that does end in the zone → append ``.``.
    * Name already absolute (``foo.example.com.``) → pass through, no rewrite.
    """
    if not raw:
        raise ValidationError(
            "RRset name is required.",
            hint="Use --name with the leaf label, FQDN, or @ for the apex.",
        )
    zone_bare = zone.rstrip(".")
    zone_apex = zone_bare + "."
    if raw == "@":
        return zone_apex, True
    if raw.endswith("."):
        return raw, False
    if raw == zone_bare or raw.endswith("." + zone_bare):
        return f"{raw}.", True
    return f"{raw}.{zone_apex}", True


def validate_ttl(ttl: int, *, context: str) -> None:
    if ttl < MIN_TTL:
        raise ValidationError(
            f"TTL {ttl} for {context} is below the provider minimum ({MIN_TTL}).",
            hint=f"Set --ttl to {MIN_TTL} or higher.",
        )


def validate_content_for_type(type_: str, content: str, *, name: str) -> None:
    t = type_.upper()
    if t == "A":
        try:
            ipaddress.IPv4Address(content)
        except (ipaddress.AddressValueError, ValueError) as exc:
            raise ValidationError(
                f"Invalid IPv4 address {content!r} for A record {name!r}.",
                hint="Use a dotted-quad IPv4, e.g. 10.0.0.1.",
            ) from exc
    elif t == "AAAA":
        try:
            ipaddress.IPv6Address(content)
        except (ipaddress.AddressValueError, ValueError) as exc:
            raise ValidationError(
                f"Invalid IPv6 address {content!r} for AAAA record {name!r}.",
                hint="Use a colon-hex IPv6, e.g. 2001:db8::1.",
            ) from exc
    elif t == "MX":
        match = _MX_PATTERN.match(content)
        if match is None:
            raise ValidationError(
                f"MX content {content!r} for {name!r} must be "
                f"`<priority> <exchange>`, e.g. `10 mail.example.com.`.",
                hint="Prefix the exchange with a numeric priority.",
            )
        priority = int(match.group(1))
        if not 0 <= priority <= 65535:
            raise ValidationError(
                f"MX priority {priority} for {name!r} is outside the valid range 0-65535.",
                hint="Use a priority between 0 and 65535 (typical values: 10, 20, 30).",
            )


def _check_cname_exclusivity(
    items: Iterable[tuple[str, str]],
    *,
    extra_hint: str = "",
) -> None:
    per_name: dict[str, set[str]] = {}
    for name, type_ in items:
        per_name.setdefault(name, set()).add(type_.upper())
    for name, types in per_name.items():
        if "CNAME" in types and any(t in CNAME_CONFLICT_TYPES for t in types):
            offenders = sorted(types - {"CNAME"})
            hint = "CNAMEs must be the only record at a label (RFC 1912 §2.4)."
            if extra_hint:
                hint += " " + extra_hint
            raise ValidationError(
                f"Label {name!r} cannot hold a CNAME together with {offenders!r}.",
                hint=hint,
            )


def enforce_cname_exclusivity(changes: list[RRsetChange]) -> None:
    """Reject any add/update that puts CNAME and a conflicting type on the same label.

    Cross-batch conflicts (CNAME already present on the server) are left to the
    API; we only see intra-batch collisions here.
    """
    items = ((c.name, c.type) for c in changes if c.changetype != "delete")
    _check_cname_exclusivity(
        items,
        extra_hint="Delete the other types in the same batch or choose a different label.",
    )


def enforce_cname_exclusivity_replacement(rrsets: list[RRsetInput]) -> None:
    _check_cname_exclusivity((r.name, r.type) for r in rrsets)


def validate_changes(changes: list[RRsetChange]) -> None:
    if len(changes) > PATCH_MAX_RRSETS:
        raise ValidationError(
            f"A single PATCH may carry at most {PATCH_MAX_RRSETS} rrsets (got {len(changes)}).",
            hint="Split the batch, or use `rc0 record import` which allows "
            f"up to {PUT_MAX_RRSETS} rrsets in one PUT.",
        )
    for change in changes:
        context = f"{change.name} {change.type}"
        validate_ttl(change.ttl, context=context)
        if change.changetype != "delete":
            for record in change.records:
                validate_content_for_type(change.type, record.content, name=change.name)
    enforce_cname_exclusivity(changes)


def validate_replacement(rrsets: list[RRsetInput]) -> None:
    if len(rrsets) > PUT_MAX_RRSETS:
        raise ValidationError(
            f"A single PUT may carry at most {PUT_MAX_RRSETS} rrsets (got {len(rrsets)}).",
            hint="Split the zone transfer or trim unchanged rrsets client-side.",
        )
    for rrset in rrsets:
        context = f"{rrset.name} {rrset.type}"
        validate_ttl(rrset.ttl, context=context)
        for record in rrset.records:
            validate_content_for_type(rrset.type, record.content, name=rrset.name)
    enforce_cname_exclusivity_replacement(rrsets)

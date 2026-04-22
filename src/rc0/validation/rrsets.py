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

from rc0.client.errors import ValidationError
from rc0.models.rrset_write import (
    CNAME_CONFLICT_TYPES,
    MIN_TTL,
    PATCH_MAX_RRSETS,
    PUT_MAX_RRSETS,
    RRsetChange,
    RRsetInput,
)

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
    zone_apex = zone.rstrip(".") + "."
    if raw == "@":
        return zone_apex, True
    if raw.endswith("."):
        return raw, False
    if raw.endswith(zone.rstrip(".")):
        return raw + ".", True
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


def enforce_cname_exclusivity(changes: list[RRsetChange]) -> None:
    """Reject any add/update that puts CNAME and a conflicting type on the same label.

    Cross-batch conflicts (CNAME already present on the server) are left to the
    API; we only see intra-batch collisions here.
    """
    per_name_live: dict[str, set[str]] = {}
    for change in changes:
        if change.changetype == "delete":
            continue
        per_name_live.setdefault(change.name, set()).add(change.type.upper())
    for name, types in per_name_live.items():
        if "CNAME" in types and any(t in CNAME_CONFLICT_TYPES for t in types):
            offenders = sorted(types - {"CNAME"})
            raise ValidationError(
                f"Label {name!r} cannot hold a CNAME together with {offenders!r}.",
                hint="CNAMEs must be the only record at a label (RFC 1912 §2.4). "
                "Delete the other types in the same batch or choose a "
                "different label.",
            )


def enforce_cname_exclusivity_replacement(rrsets: list[RRsetInput]) -> None:
    per_name: dict[str, set[str]] = {}
    for r in rrsets:
        per_name.setdefault(r.name, set()).add(r.type.upper())
    for name, types in per_name.items():
        if "CNAME" in types and any(t in CNAME_CONFLICT_TYPES for t in types):
            offenders = sorted(types - {"CNAME"})
            raise ValidationError(
                f"Label {name!r} cannot hold a CNAME together with {offenders!r}.",
                hint="CNAMEs must be the only record at a label (RFC 1912 §2.4).",
            )


def validate_changes(changes: list[RRsetChange]) -> None:
    if len(changes) > PATCH_MAX_RRSETS:
        raise ValidationError(
            f"A single PATCH may carry at most {PATCH_MAX_RRSETS} rrsets (got {len(changes)}).",
            hint="Split the batch, or use `rc0 record replace-all` which allows "
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

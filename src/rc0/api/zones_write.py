"""Zone-endpoint wrappers: write operations plus the inbound/outbound GET helpers.

The read-side of ``/zones/{zone}/inbound`` and ``/outbound`` lives here (not in
``api/zones.py``) so the three-part xfr-in / xfr-out surface (show / set /
unset) stays together. Everything else in this file is a write operation that
routes through :func:`rc0.client.mutations.execute_mutation`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rc0.client.mutations import execute_mutation
from rc0.models.zone_write import (
    CreateZoneRequest,
    InboundXfrRequest,
    OutboundXfrRequest,
    PatchZoneRequest,
    UpdateZoneRequest,
    ZoneType,
)

if TYPE_CHECKING:
    from rc0.client.dry_run import DryRunResult
    from rc0.client.http import Client
    from rc0.models.common import Rc0WriteModel


def _body(model: Rc0WriteModel) -> dict[str, Any]:
    result: dict[str, Any] = model.model_dump(exclude_none=True)
    return result


def create_zone(
    client: Client,
    *,
    domain: str,
    zone_type: ZoneType,
    masters: list[str] | None = None,
    cds_cdnskey_publish: bool | None = None,
    serial_auto_increment: bool | None = None,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    body = _body(
        CreateZoneRequest(
            domain=domain,
            type=zone_type,
            masters=masters,
            cds_cdnskey_publish=cds_cdnskey_publish,
            serial_auto_increment=serial_auto_increment,
        ),
    )
    master_note = f" with {len(masters)} master IP(s)" if masters else ""
    return execute_mutation(
        client,
        method="POST",
        path="/api/v2/zones",
        body=body,
        dry_run=dry_run,
        summary=f"Would create {zone_type} zone {domain}{master_note}.",
        side_effects=["creates_zone"],
    )


def update_zone(
    client: Client,
    *,
    zone: str,
    zone_type: ZoneType | None = None,
    masters: list[str] | None = None,
    cds_cdnskey_publish: bool | None = None,
    serial_auto_increment: bool | None = None,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    body = _body(
        UpdateZoneRequest(
            type=zone_type,
            masters=masters,
            cds_cdnskey_publish=cds_cdnskey_publish,
            serial_auto_increment=serial_auto_increment,
        ),
    )
    return execute_mutation(
        client,
        method="PUT",
        path=f"/api/v2/zones/{zone}",
        body=body,
        dry_run=dry_run,
        summary=f"Would update zone {zone}.",
    )


def patch_zone_disabled(
    client: Client,
    *,
    zone: str,
    disabled: bool,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    body = _body(PatchZoneRequest(zone_disabled=disabled))
    verb = "disable" if disabled else "enable"
    return execute_mutation(
        client,
        method="PATCH",
        path=f"/api/v2/zones/{zone}",
        body=body,
        dry_run=dry_run,
        summary=f"Would {verb} zone {zone}.",
    )


def delete_zone(
    client: Client,
    *,
    zone: str,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    return execute_mutation(
        client,
        method="DELETE",
        path=f"/api/v2/zones/{zone}",
        dry_run=dry_run,
        summary=f"Would delete zone {zone}.",
        side_effects=["deletes_zone", "discards_rrsets"],
    )


def retrieve_zone(
    client: Client,
    *,
    zone: str,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    return execute_mutation(
        client,
        method="POST",
        path=f"/api/v2/zones/{zone}/retrieve",
        dry_run=dry_run,
        summary=f"Would queue a zone transfer for {zone}.",
    )


def test_zone(
    client: Client,
    *,
    domain: str,
    zone_type: ZoneType,
    masters: list[str] | None = None,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    """POST /api/v2/zones?test=1 — the API's own validation call."""
    body = _body(
        CreateZoneRequest(domain=domain, type=zone_type, masters=masters),
    )
    return execute_mutation(
        client,
        method="POST",
        path="/api/v2/zones",
        body=body,
        params={"test": 1},
        dry_run=dry_run,
        summary=f"Would ask the API to validate {domain} ({zone_type}).",
    )


def set_inbound(
    client: Client,
    *,
    zone: str,
    tsigkey: str,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    body = _body(InboundXfrRequest(tsigkey=tsigkey))
    return execute_mutation(
        client,
        method="POST",
        path=f"/api/v2/zones/{zone}/inbound",
        body=body,
        dry_run=dry_run,
        summary=f"Would set inbound TSIG key for {zone} to {tsigkey!r}.",
    )


def unset_inbound(
    client: Client,
    *,
    zone: str,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    return execute_mutation(
        client,
        method="DELETE",
        path=f"/api/v2/zones/{zone}/inbound",
        dry_run=dry_run,
        summary=f"Would clear inbound TSIG key for {zone}.",
    )


def show_inbound(client: Client, *, zone: str) -> dict[str, Any]:
    response = client.get(f"/api/v2/zones/{zone}/inbound")
    payload: Any = response.json()
    return payload if isinstance(payload, dict) else {"data": payload}


def set_outbound(
    client: Client,
    *,
    zone: str,
    secondaries: list[str] | None,
    tsigkey: str | None,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    body = _body(
        OutboundXfrRequest(
            secondaries=secondaries or [],
            tsigkey=tsigkey or "",
        ),
    )
    return execute_mutation(
        client,
        method="POST",
        path=f"/api/v2/zones/{zone}/outbound",
        body=body,
        dry_run=dry_run,
        summary=f"Would set outbound xfr for {zone}.",
    )


def unset_outbound(
    client: Client,
    *,
    zone: str,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    return execute_mutation(
        client,
        method="DELETE",
        path=f"/api/v2/zones/{zone}/outbound",
        dry_run=dry_run,
        summary=f"Would clear outbound xfr config for {zone}.",
    )


def show_outbound(client: Client, *, zone: str) -> dict[str, Any]:
    response = client.get(f"/api/v2/zones/{zone}/outbound")
    payload: Any = response.json()
    return payload if isinstance(payload, dict) else {"data": payload}

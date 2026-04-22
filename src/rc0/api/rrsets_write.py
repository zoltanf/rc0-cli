"""Write-endpoint wrappers for /api/v2/zones/{zone}/rrsets.

All three wrappers route through :func:`rc0.client.mutations.execute_mutation`
so the dry-run/live code paths share one dispatcher (and one parity test).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rc0.client.mutations import execute_mutation
from rc0.models.rrset_write import ReplaceRRsetBody, RRsetChange, RRsetInput

if TYPE_CHECKING:
    from rc0.client.dry_run import DryRunResult
    from rc0.client.http import Client


def patch_rrsets(
    client: Client,
    *,
    zone: str,
    changes: list[RRsetChange],
    dry_run: bool,
    summary: str,
    side_effects: list[str] | None = None,
) -> DryRunResult | dict[str, Any]:
    """PATCH /api/v2/zones/{zone}/rrsets with a list-shaped body."""
    body: list[dict[str, Any]] = [c.model_dump() for c in changes]
    return execute_mutation(
        client,
        method="PATCH",
        path=f"/api/v2/zones/{zone}/rrsets",
        body=body,
        dry_run=dry_run,
        summary=summary,
        side_effects=side_effects,
    )


def put_rrsets(
    client: Client,
    *,
    zone: str,
    rrsets: list[RRsetInput],
    dry_run: bool,
    summary: str,
) -> DryRunResult | dict[str, Any]:
    """PUT /api/v2/zones/{zone}/rrsets with the ``{"rrsets":[…]}`` envelope."""
    body = ReplaceRRsetBody(rrsets=rrsets).model_dump()
    return execute_mutation(
        client,
        method="PUT",
        path=f"/api/v2/zones/{zone}/rrsets",
        body=body,
        dry_run=dry_run,
        summary=summary,
        side_effects=["replaces_zone_contents"],
    )


def clear_rrsets(
    client: Client,
    *,
    zone: str,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    """DELETE /api/v2/zones/{zone}/rrsets — wipes every rrset except SOA/NS."""
    return execute_mutation(
        client,
        method="DELETE",
        path=f"/api/v2/zones/{zone}/rrsets",
        dry_run=dry_run,
        summary=f"Would clear all non-apex rrsets from {zone}.",
        side_effects=["deletes_rrsets"],
    )

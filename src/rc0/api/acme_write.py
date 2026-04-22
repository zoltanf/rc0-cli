"""ACME mutation wrappers: add and remove DNS-01 challenge TXT records.

Both operations use PATCH /api/v1/acme/zones/{zone}/rrsets with an
UpdateRRsetRequest array body; they differ only in changetype.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rc0.client.mutations import execute_mutation

if TYPE_CHECKING:
    from rc0.client.dry_run import DryRunResult
    from rc0.client.http import Client


def add_challenge(
    client: Client,
    *,
    zone: str,
    token: str,
    ttl: int = 60,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    body = [
        {
            "name": f"_acme-challenge.{zone}.",
            "type": "TXT",
            "ttl": ttl,
            "changetype": "add",
            "records": [{"content": token}],
        }
    ]
    return execute_mutation(
        client,
        method="PATCH",
        path=f"/api/v1/acme/zones/{zone}/rrsets",
        body=body,
        dry_run=dry_run,
        summary=f"Would add ACME challenge TXT for zone {zone}.",
    )


def remove_challenge(
    client: Client,
    *,
    zone: str,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    body = [
        {
            "name": f"_acme-challenge.{zone}.",
            "type": "TXT",
            "changetype": "delete",
        }
    ]
    return execute_mutation(
        client,
        method="PATCH",
        path=f"/api/v1/acme/zones/{zone}/rrsets",
        body=body,
        dry_run=dry_run,
        summary=f"Would remove ACME challenge TXT from zone {zone}.",
    )

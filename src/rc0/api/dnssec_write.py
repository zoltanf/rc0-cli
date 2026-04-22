"""DNSSEC endpoint wrappers: sign, unsign, keyrollover, ack-ds, and simulate.

All six endpoints are POST with no request body. `sign` and `unsign` accept
query parameters. Everything routes through :func:`rc0.client.mutations.execute_mutation`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rc0.client.mutations import execute_mutation

if TYPE_CHECKING:
    from rc0.client.dry_run import DryRunResult
    from rc0.client.http import Client


def sign_zone(
    client: Client,
    *,
    zone: str,
    ignore_safety_period: bool = False,
    enable_cds_cdnskey: bool = False,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    params: dict[str, Any] = {}
    if ignore_safety_period:
        params["ignoresafetyperiod"] = "1"
    if enable_cds_cdnskey:
        params["enable_cds_cdnskey"] = "1"
    return execute_mutation(
        client,
        method="POST",
        path=f"/api/v2/zones/{zone}/sign",
        params=params or None,
        dry_run=dry_run,
        summary=f"Would sign zone {zone} with DNSSEC.",
    )


def unsign_zone(
    client: Client,
    *,
    zone: str,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    return execute_mutation(
        client,
        method="POST",
        path=f"/api/v2/zones/{zone}/unsign",
        dry_run=dry_run,
        summary=f"Would remove DNSSEC signing from zone {zone}.",
    )


def keyrollover(
    client: Client,
    *,
    zone: str,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    return execute_mutation(
        client,
        method="POST",
        path=f"/api/v2/zones/{zone}/keyrollover",
        dry_run=dry_run,
        summary=f"Would start KSK rollover for zone {zone}.",
    )


def ack_ds(
    client: Client,
    *,
    zone: str,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    return execute_mutation(
        client,
        method="POST",
        path=f"/api/v2/zones/{zone}/dsupdate",
        dry_run=dry_run,
        summary=f"Would acknowledge DS update for zone {zone}.",
    )


def simulate_dsseen(
    client: Client,
    *,
    zone: str,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    return execute_mutation(
        client,
        method="POST",
        path=f"/api/v2/zones/{zone}/simulate/dsseen",
        dry_run=dry_run,
        summary=f"Would simulate DS-seen event for zone {zone}.",
    )


def simulate_dsremoved(
    client: Client,
    *,
    zone: str,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    return execute_mutation(
        client,
        method="POST",
        path=f"/api/v2/zones/{zone}/simulate/dsremoved",
        dry_run=dry_run,
        summary=f"Would simulate DS-removed event for zone {zone}.",
    )

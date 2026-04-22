"""Write-endpoint wrappers for /api/v2/settings[...]."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rc0.client.mutations import execute_mutation

if TYPE_CHECKING:
    from rc0.client.dry_run import DryRunResult
    from rc0.client.http import Client


def set_secondaries(
    client: Client,
    *,
    ips: list[str],
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    return execute_mutation(
        client,
        method="PUT",
        path="/api/v2/settings/secondaries",
        body={"secondaries": ips},
        dry_run=dry_run,
        summary=f"Would set {len(ips)} account-wide secondary(ies).",
    )


def unset_secondaries(
    client: Client,
    *,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    return execute_mutation(
        client,
        method="DELETE",
        path="/api/v2/settings/secondaries",
        dry_run=dry_run,
        summary="Would clear account-wide secondaries.",
    )


def set_tsig_in(
    client: Client,
    *,
    tsigkey: str,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    return execute_mutation(
        client,
        method="PUT",
        path="/api/v2/settings/tsig/in",
        body={"tsigkey": tsigkey},
        dry_run=dry_run,
        summary=f"Would set account-wide inbound TSIG key to {tsigkey!r}.",
    )


def unset_tsig_in(
    client: Client,
    *,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    return execute_mutation(
        client,
        method="DELETE",
        path="/api/v2/settings/tsig/in",
        dry_run=dry_run,
        summary="Would clear account-wide inbound TSIG key.",
    )


def set_tsig_out(
    client: Client,
    *,
    tsigkey: str,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    return execute_mutation(
        client,
        method="PUT",
        path="/api/v2/settings/tsig/out",
        body={"tsigkey": tsigkey},
        dry_run=dry_run,
        summary=f"Would set account-wide outbound TSIG key to {tsigkey!r}.",
    )


def unset_tsig_out(
    client: Client,
    *,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    return execute_mutation(
        client,
        method="DELETE",
        path="/api/v2/settings/tsig/out",
        dry_run=dry_run,
        summary="Would clear account-wide outbound TSIG key.",
    )

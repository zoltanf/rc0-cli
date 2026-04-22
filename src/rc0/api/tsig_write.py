"""TSIG write-endpoint wrappers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rc0.client.mutations import execute_mutation
from rc0.models.tsig_write import AddTsigRequest, Algorithm, UpdateTsigRequest

if TYPE_CHECKING:
    from rc0.client.dry_run import DryRunResult
    from rc0.client.http import Client


def add_tsig(
    client: Client,
    *,
    name: str,
    algorithm: Algorithm,
    secret: str,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    body = AddTsigRequest(
        name=name,
        algorithm=algorithm,
        secret=secret,
    ).model_dump(exclude_none=True)
    return execute_mutation(
        client,
        method="POST",
        path="/api/v2/tsig",
        body=body,
        dry_run=dry_run,
        summary=f"Would add TSIG key {name} ({algorithm}).",
    )


def update_tsig(
    client: Client,
    *,
    name: str,
    algorithm: Algorithm,
    secret: str,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    body = UpdateTsigRequest(algorithm=algorithm, secret=secret).model_dump(exclude_none=True)
    return execute_mutation(
        client,
        method="PUT",
        path=f"/api/v2/tsig/{name}",
        body=body,
        dry_run=dry_run,
        summary=f"Would update TSIG key {name} ({algorithm}).",
    )


def delete_tsig(
    client: Client,
    *,
    name: str,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    return execute_mutation(
        client,
        method="DELETE",
        path=f"/api/v2/tsig/{name}",
        dry_run=dry_run,
        summary=f"Would delete TSIG key {name}.",
        side_effects=["deletes_tsig_key"],
    )

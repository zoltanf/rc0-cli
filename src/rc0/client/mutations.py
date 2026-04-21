"""Small dispatcher shared by every Phase-2 write command.

`execute_mutation` returns either a :class:`DryRunResult` (when dry-run is on)
or a parsed JSON response dict. Command modules stay short because of it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rc0.client.dry_run import build_dry_run

if TYPE_CHECKING:
    from rc0.client.dry_run import DryRunResult
    from rc0.client.http import Client


def execute_mutation(
    client: Client,
    *,
    method: str,
    path: str,
    body: Any = None,
    params: dict[str, Any] | None = None,
    dry_run: bool,
    summary: str,
    side_effects: list[str] | None = None,
) -> DryRunResult | dict[str, Any]:
    """Either build a DryRunResult or perform the HTTP mutation and return parsed JSON.

    Returning a union keeps both branches in one place; callers render whichever
    object they receive.  Never retried — POST/PUT/PATCH/DELETE are non-idempotent
    for our purposes per mission plan §11.
    """
    if dry_run:
        return build_dry_run(
            client,
            method=method,
            path=path,
            body=body,
            params=params,
            summary=summary,
            side_effects=side_effects,
        )
    response = client.request(method, path, params=params, json=body)
    if response.status_code == 204 or not response.content:
        return {"status": "ok"}
    payload: Any = response.json()
    if isinstance(payload, dict):
        return payload
    return {"data": payload}

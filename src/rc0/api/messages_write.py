"""Write endpoints against /api/v2/messages."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rc0.api.messages import poll_message
from rc0.client.mutations import execute_mutation

if TYPE_CHECKING:
    from rc0.client.dry_run import DryRunResult
    from rc0.client.http import Client


def ack_message(
    client: Client, *, message_id: int, dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    return execute_mutation(
        client,
        method="DELETE",
        path=f"/api/v2/messages/{message_id}",
        dry_run=dry_run,
        summary=f"Would acknowledge message {message_id}.",
    )


def ack_all(client: Client) -> list[int]:
    """Poll + ack until the queue is empty. Returns the ack'd message IDs.

    Only called on the live path. ``--dry-run`` shortcircuits in the CLI layer.
    """
    acked: list[int] = []
    while True:
        msg = poll_message(client)
        if msg is None or msg.id is None:
            return acked
        client.delete(f"/api/v2/messages/{msg.id}")
        acked.append(msg.id)

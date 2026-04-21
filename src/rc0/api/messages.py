"""Messages-endpoint wrappers (read-only)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rc0.client.pagination import iter_all, iter_pages
from rc0.models.messages import Message

if TYPE_CHECKING:
    from rc0.client.http import Client


def poll_message(client: Client) -> Message | None:
    """GET /api/v2/messages — oldest unacknowledged, or ``None`` if empty."""
    payload = client.get("/api/v2/messages").json()
    if not payload:  # {} or None
        return None
    return Message.model_validate(payload)


def list_messages(
    client: Client,
    *,
    page: int | None = None,
    page_size: int | None = None,
    fetch_all: bool = False,
) -> list[Message]:
    """GET /api/v2/messages/list — Laravel envelope."""
    effective_page_size = page_size or 50
    if fetch_all:
        rows = list(
            iter_all(client, "/api/v2/messages/list", page_size=effective_page_size),
        )
    else:
        page_iterator = iter_pages(
            client,
            "/api/v2/messages/list",
            page_size=effective_page_size,
            start_page=page or 1,
        )
        rows = next(iter(page_iterator), [])
    return [Message.model_validate(r) for r in rows]

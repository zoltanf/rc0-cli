"""Messages-endpoint wrappers (read-only)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rc0.client.pagination import fetch_page, iter_all, iter_pages
from rc0.models.messages import Message

if TYPE_CHECKING:
    from rc0.client.http import Client
    from rc0.client.pagination import PageInfo


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
    fetch_all: bool = True,
) -> list[Message]:
    """GET /api/v2/messages/list — Laravel envelope. Defaults to all pages."""
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


def list_messages_page(
    client: Client,
    *,
    page: int,
    page_size: int | None = None,
) -> tuple[list[Message], PageInfo]:
    """Fetch exactly one page of messages with pagination metadata."""
    rows, info = fetch_page(
        client,
        "/api/v2/messages/list",
        page=page,
        page_size=page_size or 50,
    )
    return [Message.model_validate(r) for r in rows], info

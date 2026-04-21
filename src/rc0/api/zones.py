"""Zone-endpoint wrappers (read-only — Phase 1)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rc0.client.pagination import iter_all, iter_pages
from rc0.models.zone import Zone, ZoneStatus

if TYPE_CHECKING:
    from collections.abc import Mapping

    from rc0.client.http import Client


def list_zones(
    client: Client,
    *,
    page: int | None = None,
    page_size: int | None = None,
    fetch_all: bool = False,
    filters: Mapping[str, Any] | None = None,
) -> list[Zone]:
    """Return zones. With ``fetch_all=True`` iterate every page."""
    effective_page_size = page_size or 50
    if fetch_all:
        return [
            Zone.model_validate(row)
            for row in iter_all(
                client,
                "/api/v2/zones",
                page_size=effective_page_size,
                params=filters,
            )
        ]
    page_iterator = iter_pages(
        client,
        "/api/v2/zones",
        page_size=effective_page_size,
        params=filters,
        start_page=page or 1,
    )
    first = next(iter(page_iterator), [])
    return [Zone.model_validate(row) for row in first]


def show_zone(client: Client, zone: str) -> Zone:
    response = client.get(f"/api/v2/zones/{zone}")
    return Zone.model_validate(response.json())


def zone_status(client: Client, zone: str) -> ZoneStatus:
    response = client.get(f"/api/v2/zones/{zone}/status")
    return ZoneStatus.model_validate(response.json())

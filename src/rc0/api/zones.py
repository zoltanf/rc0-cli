"""Zone-endpoint wrappers (read-only — Phase 1)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rc0.client.pagination import fetch_page, iter_all, iter_pages
from rc0.models.zone import Zone, ZoneStatus

if TYPE_CHECKING:
    from collections.abc import Mapping

    from rc0.client.http import Client
    from rc0.client.pagination import PageInfo


def list_zones(
    client: Client,
    *,
    page: int | None = None,
    page_size: int | None = None,
    fetch_all: bool = True,
    filters: Mapping[str, Any] | None = None,
) -> list[Zone]:
    """Return zones. Defaults to fetching every page."""
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


def list_zones_page(
    client: Client,
    *,
    page: int,
    page_size: int | None = None,
    filters: Mapping[str, Any] | None = None,
) -> tuple[list[Zone], PageInfo]:
    """Fetch exactly one page of zones with pagination metadata."""
    rows, info = fetch_page(
        client,
        "/api/v2/zones",
        page=page,
        page_size=page_size or 50,
        params=filters,
    )
    return [Zone.model_validate(row) for row in rows], info


def show_zone(client: Client, zone: str) -> Zone:
    response = client.get(f"/api/v2/zones/{zone}")
    return Zone.model_validate(response.json())


def zone_status(client: Client, zone: str) -> ZoneStatus:
    response = client.get(f"/api/v2/zones/{zone}/status")
    return ZoneStatus.model_validate(response.json())

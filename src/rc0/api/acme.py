"""ACME endpoint read wrappers (v1 API)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rc0.client.pagination import fetch_page, iter_all, iter_pages

if TYPE_CHECKING:
    from rc0.client.http import Client
    from rc0.client.pagination import PageInfo


def zone_exists(client: Client, zone: str) -> list[str]:
    """GET /api/v1/acme/{zone} — returns ["found"] if configured."""
    response = client.get(f"/api/v1/acme/{zone}")
    result: list[str] = response.json()
    return result


def list_challenges(
    client: Client,
    zone: str,
    *,
    page: int | None = None,
    page_size: int | None = None,
    fetch_all: bool = True,
) -> list[dict[str, Any]]:
    """GET /api/v1/acme/zones/{zone}/rrsets — TXT challenge records.

    Defaults to fetching every page (``page_size`` defaults to 100, matching
    the v1 ACME endpoint's own default).
    """
    effective_page_size = page_size or 100
    path = f"/api/v1/acme/zones/{zone}/rrsets"
    if fetch_all:
        return [dict(row) for row in iter_all(client, path, page_size=effective_page_size)]
    page_iter = iter_pages(client, path, page_size=effective_page_size, start_page=page or 1)
    return [dict(row) for row in next(iter(page_iter), [])]


def list_challenges_page(
    client: Client,
    zone: str,
    *,
    page: int,
    page_size: int | None = None,
) -> tuple[list[dict[str, Any]], PageInfo]:
    """Fetch exactly one page of ACME challenges with pagination metadata."""
    rows, info = fetch_page(
        client,
        f"/api/v1/acme/zones/{zone}/rrsets",
        page=page,
        page_size=page_size or 100,
    )
    return [dict(row) for row in rows], info

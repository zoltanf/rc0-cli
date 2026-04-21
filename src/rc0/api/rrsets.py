"""RRset-endpoint wrappers (read-only — Phase 1)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rc0.client.pagination import iter_all, iter_pages
from rc0.models.rrset import RRset

if TYPE_CHECKING:
    from rc0.client.http import Client


def list_rrsets(
    client: Client,
    zone: str,
    *,
    name: str | None = None,
    type: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
    fetch_all: bool = False,
) -> list[RRset]:
    """GET /api/v2/zones/{zone}/rrsets — Laravel envelope."""
    filters: dict[str, str] = {}
    if name is not None:
        filters["names"] = name
    if type is not None:
        filters["types"] = type
    path = f"/api/v2/zones/{zone}/rrsets"
    effective_page_size = page_size or 50
    if fetch_all:
        rows = list(
            iter_all(client, path, page_size=effective_page_size, params=filters),
        )
    else:
        page_iterator = iter_pages(
            client,
            path,
            page_size=effective_page_size,
            params=filters,
            start_page=page or 1,
        )
        rows = next(iter(page_iterator), [])
    return [RRset.model_validate(r) for r in rows]

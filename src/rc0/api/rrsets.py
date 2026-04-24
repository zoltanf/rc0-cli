"""RRset-endpoint wrappers (read-only — Phase 1)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rc0.client.pagination import fetch_page, iter_all, iter_pages
from rc0.models.rrset import RRset

if TYPE_CHECKING:
    from rc0.client.http import Client
    from rc0.client.pagination import PageInfo


def _filters(name: str | None, type_: str | None) -> dict[str, str]:
    out: dict[str, str] = {}
    if name is not None:
        out["names"] = name
    if type_ is not None:
        out["types"] = type_
    return out


def list_rrsets(
    client: Client,
    zone: str,
    *,
    name: str | None = None,
    type: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
    fetch_all: bool = True,
) -> list[RRset]:
    """GET /api/v2/zones/{zone}/rrsets — Laravel envelope.

    ``fetch_all`` defaults to ``True`` so the caller receives every RRset.
    Pass ``fetch_all=False`` (or use :func:`list_rrsets_page`) to get one
    explicit page.
    """
    filters = _filters(name, type)
    path = f"/api/v2/zones/{zone}/rrsets"
    effective_page_size = page_size or 50
    if fetch_all:
        rows = list(iter_all(client, path, page_size=effective_page_size, params=filters))
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


def list_rrsets_page(
    client: Client,
    zone: str,
    *,
    name: str | None = None,
    type: str | None = None,
    page: int,
    page_size: int | None = None,
) -> tuple[list[RRset], PageInfo]:
    """Fetch exactly one page and return rows plus pagination metadata."""
    filters = _filters(name, type)
    path = f"/api/v2/zones/{zone}/rrsets"
    rows, info = fetch_page(
        client,
        path,
        page=page,
        page_size=page_size or 50,
        params=filters,
    )
    return [RRset.model_validate(r) for r in rows], info

"""TSIG-endpoint wrappers (read-only — Phase 1)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rc0.client.pagination import fetch_page, iter_all, iter_pages
from rc0.models.tsig import TsigKey

if TYPE_CHECKING:
    from rc0.client.http import Client
    from rc0.client.pagination import PageInfo


def list_tsig(
    client: Client,
    *,
    page: int | None = None,
    page_size: int | None = None,
    fetch_all: bool = True,
) -> list[TsigKey]:
    """GET /api/v2/tsig — bare array. Defaults to fetching every page."""
    effective_page_size = page_size or 50
    if fetch_all:
        rows = list(iter_all(client, "/api/v2/tsig", page_size=effective_page_size))
    else:
        page_iterator = iter_pages(
            client,
            "/api/v2/tsig",
            page_size=effective_page_size,
            start_page=page or 1,
        )
        rows = next(iter(page_iterator), [])
    return [TsigKey.model_validate(r) for r in rows]


def list_tsig_page(
    client: Client,
    *,
    page: int,
    page_size: int | None = None,
) -> tuple[list[TsigKey], PageInfo]:
    """Fetch exactly one page of TSIG keys with pagination metadata."""
    rows, info = fetch_page(
        client,
        "/api/v2/tsig",
        page=page,
        page_size=page_size or 50,
    )
    return [TsigKey.model_validate(r) for r in rows], info


def show_tsig(client: Client, name: str) -> TsigKey:
    """GET /api/v2/tsig/{keyname}."""
    response = client.get(f"/api/v2/tsig/{name}")
    return TsigKey.model_validate(response.json())


def list_tsig_out_deprecated(client: Client) -> dict[str, Any]:
    """GET /api/v2/tsig/out — deprecated. Returns the raw response dict.

    The spec example is a single object with ``default_key``, not an array, so
    we don't parse it through a model here.
    """
    payload: dict[str, Any] = client.get("/api/v2/tsig/out").json()
    return payload

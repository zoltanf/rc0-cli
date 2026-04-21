"""Auto-pagination helpers used by read-only list commands.

The RcodeZero API v2 accepts ``page`` (1-indexed) and ``page_size`` query
parameters on listing endpoints. Responses are JSON arrays; when a page
returns fewer rows than ``page_size`` we've hit the end.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rc0.client.errors import RequestSummary, ServerError

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from rc0.client.http import Client

DEFAULT_PAGE_SIZE = 50


def iter_pages(
    client: Client,
    path: str,
    *,
    page_size: int = DEFAULT_PAGE_SIZE,
    params: Mapping[str, Any] | None = None,
    start_page: int = 1,
) -> Iterator[list[dict[str, Any]]]:
    """Yield successive pages until a short page signals the end."""
    if page_size <= 0:
        msg = f"page_size must be positive, got {page_size}."
        raise ValueError(msg)
    page = start_page
    while True:
        query: dict[str, Any] = dict(params) if params else {}
        query["page"] = page
        query["page_size"] = page_size
        response = client.get(path, params=query)
        payload = response.json()
        if not isinstance(payload, list):
            raise ServerError(
                f"Expected JSON array from {path}, got {type(payload).__name__}.",
                request=RequestSummary(method="GET", url=f"{client.api_url}{path}"),
            )
        yield payload
        if len(payload) < page_size:
            return
        page += 1


def iter_all(
    client: Client,
    path: str,
    *,
    page_size: int = DEFAULT_PAGE_SIZE,
    params: Mapping[str, Any] | None = None,
) -> Iterator[dict[str, Any]]:
    """Flatten :func:`iter_pages` into a row iterator."""
    for page in iter_pages(client, path, page_size=page_size, params=params):
        yield from page

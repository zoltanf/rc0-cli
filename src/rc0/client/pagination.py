"""Auto-pagination helpers used by read-only list commands.

The RcodeZero API v2 uses two shapes for listing responses. This module
speaks both transparently so callers always receive per-page lists of
dicts regardless of the underlying wire shape.

1. **Laravel pagination envelope** — ``{"data": [...], "current_page": N,
   "last_page": M, "per_page": K, "total": T, ...}`` — used by
   ``/api/v2/zones``, ``/zones/{zone}/rrsets``, ``/messages/list``, and
   ``/reports/problematiczones``.
2. **Bare JSON array** — used by ``/api/v2/tsig``, ``/stats/querycounts``,
   ``/stats/topzones``, ``/reports/nxdomains``.

The ``page``/``page_size`` query parameters are authoritative over anything
in ``params``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from rc0.client.errors import RequestSummary, ServerError

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from rc0.client.http import Client

DEFAULT_PAGE_SIZE = 50


@dataclass(frozen=True)
class PageInfo:
    """Pagination metadata from a single response.

    Envelope responses populate every field from the server payload.
    Bare-array responses set ``last_page`` and ``total`` to ``None`` —
    callers must treat those as "cannot determine from here".
    """

    current_page: int
    last_page: int | None
    per_page: int
    total: int | None
    is_envelope: bool


def iter_pages(
    client: Client,
    path: str,
    *,
    page_size: int = DEFAULT_PAGE_SIZE,
    params: Mapping[str, Any] | None = None,
    start_page: int = 1,
) -> Iterator[list[dict[str, Any]]]:
    """Yield successive pages as lists of row dicts.

    Handles both the Laravel envelope (stops on ``current_page >= last_page``)
    and the bare-array shape (stops on a short page).
    """
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

        if isinstance(payload, dict) and isinstance(payload.get("data"), list):
            rows = [row for row in payload["data"] if isinstance(row, dict)]
            yield rows
            if not rows:
                return
            current_page = int(payload.get("current_page", page))
            last_page = int(payload.get("last_page", current_page))
            if current_page >= last_page:
                return
            page = current_page + 1
            continue

        if isinstance(payload, list):
            rows = [row for row in payload if isinstance(row, dict)]
            yield rows
            if len(rows) < page_size:
                return
            page += 1
            continue

        raise ServerError(
            f"Expected JSON array or paginated envelope from {path}, got {type(payload).__name__}.",
            request=RequestSummary(method="GET", url=f"{client.api_url}{path}"),
        )


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


def fetch_page(
    client: Client,
    path: str,
    *,
    page: int,
    page_size: int = DEFAULT_PAGE_SIZE,
    params: Mapping[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], PageInfo]:
    """Fetch exactly one page of rows and report pagination metadata.

    Unlike :func:`iter_pages`, this makes a single HTTP request and returns
    the rows alongside a :class:`PageInfo` describing what the server said
    about the overall pagination state — so callers can tell the user
    whether more rows exist beyond the page they asked for.
    """
    if page_size <= 0:
        msg = f"page_size must be positive, got {page_size}."
        raise ValueError(msg)
    if page <= 0:
        msg = f"page must be positive, got {page}."
        raise ValueError(msg)

    query: dict[str, Any] = dict(params) if params else {}
    query["page"] = page
    query["page_size"] = page_size
    response = client.get(path, params=query)
    payload = response.json()

    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        rows = [row for row in payload["data"] if isinstance(row, dict)]
        current_page = int(payload.get("current_page", page))
        last_page_raw = payload.get("last_page")
        last_page = int(last_page_raw) if last_page_raw is not None else current_page
        total_raw = payload.get("total")
        total = int(total_raw) if total_raw is not None else None
        info = PageInfo(
            current_page=current_page,
            last_page=last_page,
            per_page=int(payload.get("per_page", page_size)),
            total=total,
            is_envelope=True,
        )
        return rows, info

    if isinstance(payload, list):
        rows = [row for row in payload if isinstance(row, dict)]
        info = PageInfo(
            current_page=page,
            last_page=None,
            per_page=page_size,
            total=None,
            is_envelope=False,
        )
        return rows, info

    raise ServerError(
        f"Expected JSON array or paginated envelope from {path}, got {type(payload).__name__}.",
        request=RequestSummary(method="GET", url=f"{client.api_url}{path}"),
    )

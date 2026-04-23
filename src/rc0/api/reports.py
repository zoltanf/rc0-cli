"""Report-endpoint wrappers (read-only — Phase 1).

Most report endpoints return bare JSON arrays. ``problematiczones`` returns
a Laravel pagination envelope and supports ``page``/``page_size``. The
other endpoints accept query filters (``day``, ``month``, ``include_nx``)
but do not paginate.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

from rc0.client.pagination import iter_all, iter_pages
from rc0.models.reports import (
    AccountingRow,
    DomainListRow,
    NxdomainRow,
    ProblematicZone,
    QueryRateRow,
)

if TYPE_CHECKING:
    from rc0.client.http import Client


def _resolve_day(day: str | None) -> str | None:
    """Translate 'today'/'yesterday' to ISO-format dates; pass other values through."""
    if day == "today":
        return date.today().isoformat()
    if day == "yesterday":
        return (date.today() - timedelta(days=1)).isoformat()
    return day


def list_problematic_zones(
    client: Client,
    *,
    page: int | None = None,
    page_size: int | None = None,
    fetch_all: bool = False,
) -> list[ProblematicZone]:
    """Return problematic-zone rows. With ``fetch_all=True`` iterate every page."""
    effective_page_size = page_size or 50
    path = "/api/v2/reports/problematiczones"
    if fetch_all:
        return [
            ProblematicZone.model_validate(row)
            for row in iter_all(client, path, page_size=effective_page_size)
        ]
    page_iterator = iter_pages(
        client,
        path,
        page_size=effective_page_size,
        start_page=page or 1,
    )
    first = next(iter(page_iterator), [])
    return [ProblematicZone.model_validate(row) for row in first]


def list_nxdomains(client: Client, *, day: str | None = None) -> list[NxdomainRow]:
    """GET /api/v2/reports/nxdomains — bare array."""
    params: dict[str, Any] = {}
    resolved_day = _resolve_day(day)
    if resolved_day is not None:
        params["day"] = resolved_day
    response = client.get("/api/v2/reports/nxdomains", params=params or None)
    if not response.content:
        return []
    return [NxdomainRow.model_validate(r) for r in response.json()]


def list_accounting(client: Client, *, month: str | None = None) -> list[AccountingRow]:
    """GET /api/v2/reports/accounting — bare array."""
    params: dict[str, Any] = {}
    if month is not None:
        params["month"] = month
    response = client.get("/api/v2/reports/accounting", params=params or None)
    if not response.content:
        return []
    return [AccountingRow.model_validate(r) for r in response.json()]


def list_queryrates(
    client: Client,
    *,
    month: str | None = None,
    day: str | None = None,
    include_nx: bool = False,
) -> list[QueryRateRow]:
    """GET /api/v2/reports/queryrates — bare array."""
    params: dict[str, Any] = {}
    if month is not None:
        params["month"] = month
    resolved_day = _resolve_day(day)
    if resolved_day is not None:
        params["day"] = resolved_day
    if include_nx:
        params["include_nx"] = "1"
    response = client.get("/api/v2/reports/queryrates", params=params or None)
    if not response.content:
        return []
    return [QueryRateRow.model_validate(r) for r in response.json()]


def list_domainlist(client: Client) -> list[DomainListRow]:
    """GET /api/v2/reports/domainlist — bare array."""
    response = client.get("/api/v2/reports/domainlist")
    return [DomainListRow.model_validate(r) for r in response.json()]

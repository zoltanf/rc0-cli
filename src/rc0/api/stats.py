"""Stats-endpoint wrappers (read-only — Phase 1).

All stats endpoints return bare JSON arrays of row objects. None use
pagination — they're time-series / top-N responses — so each wrapper does
a single GET and parses the array into model instances.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rc0.models.stats import (
    CountryRow,
    QueryCountRow,
    TopMagnitudeRow,
    TopNxdomainRow,
    TopQnameRow,
    TopzoneRow,
    ZoneMagnitudeRow,
    ZoneNxdomainRow,
    ZoneQnameRow,
    ZoneQueryRow,
)

if TYPE_CHECKING:
    from rc0.client.http import Client


def list_querycounts(client: Client, *, days: int | None = None) -> list[QueryCountRow]:
    """GET /api/v2/stats/querycounts — bare array.

    ``days`` (1-180) selects the size of the lookback window. The API
    defaults to 30 when the parameter is omitted.
    """
    params: dict[str, Any] = {}
    if days is not None:
        params["days"] = days
    return [
        QueryCountRow.model_validate(r)
        for r in client.get("/api/v2/stats/querycounts", params=params).json()
    ]


def list_topzones(client: Client, *, days: int | None = None) -> list[TopzoneRow]:
    """GET /api/v2/stats/topzones — bare array.

    ``days`` (1-180) selects the size of the lookback window. The API
    defaults to 30 when the parameter is omitted.
    """
    params: dict[str, Any] = {}
    if days is not None:
        params["days"] = days
    return [
        TopzoneRow.model_validate(r)
        for r in client.get("/api/v2/stats/topzones", params=params).json()
    ]


def list_countries(client: Client) -> list[CountryRow]:
    """GET /api/v2/stats/countries — bare array."""
    return [CountryRow.model_validate(r) for r in client.get("/api/v2/stats/countries").json()]


def list_topmagnitude(client: Client) -> list[TopMagnitudeRow]:
    """[DEPRECATED] GET /api/v2/stats/topmagnitude — bare array."""
    return [
        TopMagnitudeRow.model_validate(r) for r in client.get("/api/v2/stats/topmagnitude").json()
    ]


def list_topnxdomains(client: Client) -> list[TopNxdomainRow]:
    """[DEPRECATED] GET /api/v2/stats/topnxdomains — bare array."""
    return [
        TopNxdomainRow.model_validate(r) for r in client.get("/api/v2/stats/topnxdomains").json()
    ]


def list_topqnames(client: Client) -> list[TopQnameRow]:
    """[DEPRECATED] GET /api/v2/stats/topqnames — bare array."""
    return [TopQnameRow.model_validate(r) for r in client.get("/api/v2/stats/topqnames").json()]


def list_zone_queries(client: Client, zone: str) -> list[ZoneQueryRow]:
    """GET /api/v2/zones/{zone}/stats/queries — bare array."""
    return [
        ZoneQueryRow.model_validate(r)
        for r in client.get(f"/api/v2/zones/{zone}/stats/queries").json()
    ]


def list_zone_magnitude(client: Client, zone: str) -> list[ZoneMagnitudeRow]:
    """[DEPRECATED] GET /api/v2/zones/{zone}/stats/magnitude — bare array."""
    return [
        ZoneMagnitudeRow.model_validate(r)
        for r in client.get(f"/api/v2/zones/{zone}/stats/magnitude").json()
    ]


def list_zone_nxdomains(client: Client, zone: str) -> list[ZoneNxdomainRow]:
    """[DEPRECATED] GET /api/v2/zones/{zone}/stats/nxdomains — bare array."""
    return [
        ZoneNxdomainRow.model_validate(r)
        for r in client.get(f"/api/v2/zones/{zone}/stats/nxdomains").json()
    ]


def list_zone_qnames(client: Client, zone: str) -> list[ZoneQnameRow]:
    """[DEPRECATED] GET /api/v2/zones/{zone}/stats/qnames — bare array."""
    return [
        ZoneQnameRow.model_validate(r)
        for r in client.get(f"/api/v2/zones/{zone}/stats/qnames").json()
    ]

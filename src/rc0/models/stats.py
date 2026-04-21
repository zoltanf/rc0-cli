"""Stats row models — one class per distinct row shape.

The stats endpoints return bare arrays of row objects. All models inherit
from :class:`Rc0Model`, which sets ``extra="allow"`` so any fields returned
by the API (and not declared here) flow through model_dump unchanged.

Deprecated endpoints whose spec has no example are modelled as empty
subclasses — they accept any shape and render every field via extras.
"""

from __future__ import annotations

from rc0.models.common import Rc0Model


class QueryCountRow(Rc0Model):
    """One day of account-wide query counts. API: /api/v2/stats/querycounts."""

    date: str | None = None
    count: int | None = None
    nxcount: int | None = None


class TopzoneRow(Rc0Model):
    """One row of the top-zones list. API: /api/v2/stats/topzones."""


class CountryRow(Rc0Model):
    """One row of the per-country counts. API: /api/v2/stats/countries."""

    cc: str | None = None
    country: str | None = None
    qc: int | None = None
    region: str | None = None
    subregion: str | None = None


class TopMagnitudeRow(Rc0Model):
    """[DEPRECATED] Row from /api/v2/stats/topmagnitude. Spec has no example."""


class TopNxdomainRow(Rc0Model):
    """[DEPRECATED] Row from /api/v2/stats/topnxdomains. Spec has no example."""


class TopQnameRow(Rc0Model):
    """[DEPRECATED] Row from /api/v2/stats/topqnames. Spec has no example."""


class ZoneQueryRow(Rc0Model):
    """One day of per-zone queries. API: /api/v2/zones/{zone}/stats/queries."""

    date: str | None = None
    qcount: int | None = None
    nxcount: int | None = None


class ZoneMagnitudeRow(Rc0Model):
    """[DEPRECATED] One day of per-zone magnitude.

    API: /api/v2/zones/{zone}/stats/magnitude.
    """

    date: str | None = None
    mag: float | None = None


class ZoneNxdomainRow(Rc0Model):
    """[DEPRECATED] Row from /api/v2/zones/{zone}/stats/nxdomains."""


class ZoneQnameRow(Rc0Model):
    """[DEPRECATED] Row from /api/v2/zones/{zone}/stats/qnames."""

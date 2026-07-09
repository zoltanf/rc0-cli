"""RcodeZero location (site) row model. API: /api/v2/sites."""

from __future__ import annotations

from rc0.models.common import Rc0Model


class Site(Rc0Model):
    """One RcodeZero anycast location. API: GET /api/v2/sites.

    ``state``/``statecode`` are only populated for US locations. ``clouds``
    lists the anycast clouds (e.g. ``cloud1``/``cloud2``) serving the site.
    """

    name: str | None = None
    city: str | None = None
    countrycode: str | None = None
    country: str | None = None
    continentcode: str | None = None
    continent: str | None = None
    state: str | None = None
    statecode: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    status: str | None = None
    clouds: list[str] | None = None

"""Zone and ZoneStatus — mirrors the /api/v2/zones response schema.

The API returns uppercase ``type`` values ("MASTER", "SLAVE"); we keep the
raw string so callers can pattern-match or print it as-is.
"""

from __future__ import annotations

from typing import Any

from rc0.models.common import Rc0Model


class Zone(Rc0Model):
    id: int | None = None
    domain: str
    type: str | None = None
    dnssec: str | None = None
    created: str | None = None
    last_check: str | None = None
    serial: int | None = None
    masters: list[str] | None = None
    nsset: list[str] | None = None
    outbound_xfr_host: dict[str, Any] | None = None
    zone_disabled: bool | None = None


class ZoneStatus(Rc0Model):
    domain: str | None = None
    serial: int | None = None
    status: str | None = None
    zone_disabled: bool | None = None

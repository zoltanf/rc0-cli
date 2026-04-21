"""Zone and ZoneStatus — mirrors #/components/schemas/Zone in the pinned spec."""

from __future__ import annotations

from rc0.models.common import Rc0Model


class Zone(Rc0Model):
    domain: str
    type: str = "master"
    dnssec: str | None = None
    created: str | None = None
    last_check: str | None = None


class ZoneStatus(Rc0Model):
    domain: str
    serial: int | None = None
    status: str | None = None

"""Account settings model — GET /api/v2/settings returns a single object."""

from __future__ import annotations

from rc0.models.common import Rc0Model


class AccountSettings(Rc0Model):
    secondaries: list[str] | None = None
    tsigin: str | None = None
    tsigout: str | None = None

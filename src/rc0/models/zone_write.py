"""Pydantic request bodies for POST/PUT/PATCH on /api/v2/zones[...]."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from rc0.models.common import Rc0WriteModel

ZoneType = Literal["master", "slave"]


class CreateZoneRequest(Rc0WriteModel):
    domain: str
    type: ZoneType
    masters: list[str] | None = None
    cds_cdnskey_publish: bool | None = None
    serial_auto_increment: bool | None = None


class UpdateZoneRequest(Rc0WriteModel):
    type: ZoneType | None = None
    masters: list[str] | None = None
    cds_cdnskey_publish: bool | None = None
    serial_auto_increment: bool | None = None


class PatchZoneRequest(Rc0WriteModel):
    zone_disabled: bool


class InboundXfrRequest(Rc0WriteModel):
    tsigkey: str


class OutboundXfrRequest(Rc0WriteModel):
    """Outbound transfer config.

    Empty values are semantically meaningful: the API uses
    ``{"secondaries": [], "tsigkey": ""}`` to *clear* an existing config.
    We use non-``None`` defaults (``[]`` and ``""``) so they survive
    ``model_dump(exclude_none=True)`` in :func:`rc0.api.zones_write._body`.
    """

    secondaries: list[str] = Field(default_factory=list)
    tsigkey: str = ""

"""Pydantic request bodies and client-side limits for the /rrsets endpoints.

These models mirror the v2 OpenAPI schemas:

* :class:`RRsetChange` ↔ ``UpdateRRsetRequest`` (used in PATCH body array).
* :class:`RRsetInput`  ↔ ``RRSets``             (used in PUT body array).
* :class:`ReplaceRRsetBody` ↔ ``ReplaceRRsetRequest``.

Mission plan §12 pins the size and TTL limits, so they live here as module-level
constants alongside the models that use them.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from rc0.models.common import Rc0WriteModel

ChangeType = Literal["add", "update", "delete"]

PATCH_MAX_RRSETS: int = 1000
PUT_MAX_RRSETS: int = 3000
MIN_TTL: int = 60

CNAME_CONFLICT_TYPES: frozenset[str] = frozenset(
    {
        "A",
        "AAAA",
        "AFSDB",
        "ALIAS",
        "CAA",
        "CERT",
        "DNAME",
        "DS",
        "HINFO",
        "HTTPS",
        "LOC",
        "MX",
        "NAPTR",
        "NS",
        "PTR",
        "RP",
        "SMIMEA",
        "SPF",
        "SRV",
        "SSHFP",
        "SVCB",
        "TLSA",
        "TXT",
        "URI",
    },
)


class RecordInput(Rc0WriteModel):
    content: str
    disabled: bool = False


class RRsetChange(Rc0WriteModel):
    name: str
    type: str
    ttl: int
    changetype: ChangeType
    records: list[RecordInput] = Field(default_factory=list)


class RRsetInput(Rc0WriteModel):
    name: str
    type: str
    ttl: int
    records: list[RecordInput] = Field(default_factory=list)


class ReplaceRRsetBody(Rc0WriteModel):
    rrsets: list[RRsetInput] = Field(default_factory=list)

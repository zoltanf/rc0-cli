"""Pydantic request bodies for POST/PUT on /api/v2/tsig[...]."""

from __future__ import annotations

from typing import Literal

from rc0.models.common import Rc0WriteModel

TSIG_ALGORITHMS: tuple[str, ...] = (
    "hmac-md5",
    "hmac-sha1",
    "hmac-sha224",
    "hmac-sha256",
    "hmac-sha384",
    "hmac-sha512",
)

Algorithm = Literal[
    "hmac-md5",
    "hmac-sha1",
    "hmac-sha224",
    "hmac-sha256",
    "hmac-sha384",
    "hmac-sha512",
]


class AddTsigRequest(Rc0WriteModel):
    name: str
    algorithm: Algorithm
    secret: str


class UpdateTsigRequest(Rc0WriteModel):
    algorithm: Algorithm
    secret: str

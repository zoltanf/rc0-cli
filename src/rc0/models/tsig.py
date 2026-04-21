"""TSIG key model — mirrors #/components/schemas/TsigKeyObject."""

from __future__ import annotations

from rc0.models.common import Rc0Model


class TsigKey(Rc0Model):
    """A TSIG key record.

    The field is called ``name`` on the wire, not ``keyname``; the URL
    path parameter ``{keyname}`` is just REST convention.
    """

    id: int | None = None
    name: str
    algorithm: str | None = None
    secret: str | None = None
    default_key: bool | None = None

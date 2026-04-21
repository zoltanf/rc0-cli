"""RRset and Record models — #/components/schemas/RRset."""

from __future__ import annotations

from pydantic import Field

from rc0.models.common import Rc0Model


class Record(Rc0Model):
    content: str
    disabled: bool = False


class RRset(Rc0Model):
    name: str
    type: str
    ttl: int = 3600
    records: list[Record] = Field(default_factory=list)

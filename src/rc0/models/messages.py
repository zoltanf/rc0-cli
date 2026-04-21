"""Message model — /api/v2/messages and /api/v2/messages/list."""

from __future__ import annotations

from rc0.models.common import Rc0Model


class Message(Rc0Model):
    id: int | None = None
    domain: str | None = None
    date: str | None = None
    type: str | None = None
    comment: str | None = None

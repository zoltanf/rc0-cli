"""Sites-endpoint wrapper (read-only).

``/api/v2/sites`` returns a ``{"sites": [...]}`` envelope listing every
RcodeZero anycast location with GPS coordinates and cloud assignments.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rc0.models.sites import Site

if TYPE_CHECKING:
    from rc0.client.http import Client


def list_sites(client: Client) -> list[Site]:
    """GET /api/v2/sites — returns the ``sites`` array from the envelope."""
    response = client.get("/api/v2/sites")
    if not response.content.strip():
        return []
    payload = response.json()
    rows = payload.get("sites", []) if isinstance(payload, dict) else payload
    return [Site.model_validate(row) for row in rows]

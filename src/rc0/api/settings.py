"""Account-settings endpoint wrapper."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rc0.models.settings import AccountSettings

if TYPE_CHECKING:
    from rc0.client.http import Client


def show_settings(client: Client) -> AccountSettings:
    """GET /api/v2/settings — single object."""
    return AccountSettings.model_validate(client.get("/api/v2/settings").json())

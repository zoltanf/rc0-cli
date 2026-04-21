"""Round-trip representative payloads against the Pydantic models."""

from __future__ import annotations

from rc0.models.zone import Zone, ZoneStatus


def test_zone_parses_minimum_payload() -> None:
    z = Zone.model_validate(
        {"domain": "example.com", "type": "master", "dnssec": "yes"},
    )
    assert z.domain == "example.com"
    assert z.type == "master"


def test_zone_status_parses() -> None:
    s = ZoneStatus.model_validate(
        {"domain": "example.com", "serial": 1, "status": "ok"},
    )
    assert s.serial == 1

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


def test_zone_parses_full_payload() -> None:
    z = Zone.model_validate(
        {
            "id": 42,
            "domain": "testzone144.at",
            "type": "SLAVE",
            "dnssec": "no",
            "serial": 2026042100,
            "masters": ["10.0.0.1"],
            "nsset": ["ns1.example.com."],
            "outbound_xfr_host": {"ips": ["1.2.3.4"], "port": 53},
            "zone_disabled": False,
        },
    )
    assert z.id == 42
    assert z.type == "SLAVE"
    assert z.serial == 2026042100
    assert z.masters == ["10.0.0.1"]
    assert z.outbound_xfr_host == {"ips": ["1.2.3.4"], "port": 53}


def test_zone_type_accepts_any_string() -> None:
    z = Zone.model_validate({"domain": "x", "type": "slave"})
    assert z.type == "slave"


def test_zone_defaults_are_none() -> None:
    z = Zone.model_validate({"domain": "x"})
    assert z.type is None
    assert z.dnssec is None
    assert z.serial is None


def test_zone_status_accepts_partial_payload() -> None:
    s = ZoneStatus.model_validate({"zone_disabled": False})
    assert s.zone_disabled is False
    assert s.domain is None

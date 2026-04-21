"""BIND zone-file renderer."""

from __future__ import annotations

from rc0.output.bind import render_rrsets


def test_bind_renders_apex_soa_ns_and_a() -> None:
    out = render_rrsets(
        zone="example.com",
        rrsets=[
            {
                "name": "example.com.",
                "type": "SOA",
                "ttl": 3600,
                "records": [
                    {
                        "content": "ns1.example.com. admin.example.com. 1 7200 3600 1209600 3600",
                        "disabled": False,
                    }
                ],
            },
            {
                "name": "example.com.",
                "type": "NS",
                "ttl": 3600,
                "records": [
                    {"content": "ns1.example.com.", "disabled": False},
                    {"content": "ns2.example.com.", "disabled": False},
                ],
            },
            {
                "name": "www.example.com.",
                "type": "A",
                "ttl": 300,
                "records": [{"content": "10.0.0.1", "disabled": False}],
            },
        ],
    )
    assert "$ORIGIN example.com." in out
    assert "SOA" in out
    assert "10.0.0.1" in out


def test_bind_skips_disabled_records() -> None:
    out = render_rrsets(
        zone="example.com",
        rrsets=[
            {
                "name": "www.example.com.",
                "type": "A",
                "ttl": 300,
                "records": [
                    {"content": "10.0.0.1", "disabled": False},
                    {"content": "10.0.0.9", "disabled": True},
                ],
            }
        ],
    )
    assert "10.0.0.1" in out
    assert "10.0.0.9" not in out

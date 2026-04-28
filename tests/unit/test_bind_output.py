"""BIND zone-file renderer."""

from __future__ import annotations

import io

import dns.name
import dns.rdatatype
import dns.zone

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


def _reassemble_txt(zone_text: str, name: str, *, zone: str) -> bytes:
    """Round-trip the rendered zone and concatenate the TXT strings at ``name``."""
    z = dns.zone.from_text(
        zone_text,
        origin=zone.rstrip(".") + ".",
        relativize=False,
        check_origin=False,
    )
    rds = z.find_rdataset(dns.name.from_text(name), dns.rdatatype.TXT)
    rdata = next(iter(rds))
    return b"".join(rdata.strings)


def test_bind_renders_long_txt_record() -> None:
    """2048-bit DKIM keys exceed 255 bytes; render must chunk, not crash."""
    long_dkim = (
        "v=DKIM1; k=rsa; p=" + "A" * 600  # ~620 bytes total — well past the 255 limit
    )
    out = render_rrsets(
        zone="bonsy.com",
        rrsets=[
            {
                "name": "google._domainkey.bonsy.com.",
                "type": "TXT",
                "ttl": 3600,
                "records": [{"content": f'"{long_dkim}"', "disabled": False}],
            },
        ],
    )
    assert "google._domainkey" in out
    reassembled = _reassemble_txt(out, "google._domainkey.bonsy.com.", zone="bonsy.com")
    assert reassembled == long_dkim.encode()


def test_bind_preserves_multi_string_txt() -> None:
    """Pre-chunked input ``"part1" "part2"`` must round-trip with both segments."""
    content = '"part1" "part2"'
    out = render_rrsets(
        zone="example.com",
        rrsets=[
            {
                "name": "txt.example.com.",
                "type": "TXT",
                "ttl": 3600,
                "records": [{"content": content, "disabled": False}],
            },
        ],
    )
    reassembled = _reassemble_txt(out, "txt.example.com.", zone="example.com")
    assert reassembled == b"part1part2"


def test_bind_continues_after_record_render_failure(capsys) -> None:
    """A single broken record must not nuke the rest of the export."""
    out = render_rrsets(
        zone="example.com",
        rrsets=[
            {
                "name": "broken.example.com.",
                "type": "A",
                "ttl": 300,
                "records": [{"content": "not-an-ip-address", "disabled": False}],
            },
            {
                "name": "good.example.com.",
                "type": "A",
                "ttl": 300,
                "records": [{"content": "10.0.0.1", "disabled": False}],
            },
        ],
    )
    assert "10.0.0.1" in out
    captured = capsys.readouterr()
    assert "warning: skipped record at broken.example.com." in captured.err


def test_bind_round_trips_to_zone_object() -> None:
    """Rendered output must be parseable as a zone file."""
    out = render_rrsets(
        zone="example.com",
        rrsets=[
            {
                "name": "example.com.",
                "type": "SOA",
                "ttl": 3600,
                "records": [
                    {
                        "content": ("ns1.example.com. admin.example.com. 1 7200 3600 1209600 3600"),
                        "disabled": False,
                    }
                ],
            },
            {
                "name": "long._domainkey.example.com.",
                "type": "TXT",
                "ttl": 3600,
                "records": [{"content": '"' + "x" * 1000 + '"', "disabled": False}],
            },
        ],
    )
    z = dns.zone.from_text(out, origin="example.com.", relativize=False, check_origin=False)
    assert z.find_rdataset(dns.name.from_text("long._domainkey.example.com."), dns.rdatatype.TXT)
    # Sanity: the underlying io path also works
    io.StringIO(out).getvalue()

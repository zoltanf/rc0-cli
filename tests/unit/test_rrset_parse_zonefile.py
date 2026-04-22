"""Tests for rc0.rrsets.parse.from_zonefile (BIND)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from rc0.client.errors import ValidationError
from rc0.rrsets.parse import from_zonefile

if TYPE_CHECKING:
    from pathlib import Path


def test_from_zonefile_basic(tmp_path: Path) -> None:
    zf = tmp_path / "example.com.zone"
    zf.write_text(
        "$ORIGIN example.com.\n"
        "$TTL 3600\n"
        "@     IN SOA ns1.example.com. admin.example.com. 1 7200 3600 1209600 3600\n"
        "@     IN NS  ns1.example.com.\n"
        "@     IN NS  ns2.example.com.\n"
        "www   IN A   10.0.0.1\n"
        "www   IN A   10.0.0.2\n"
        "mail  IN MX  10 mx.example.com.\n",
    )
    rrsets = from_zonefile(zf, zone="example.com")
    by_name_type = {(r.name, r.type): r for r in rrsets}
    assert ("example.com.", "SOA") in by_name_type
    ns = by_name_type[("example.com.", "NS")]
    assert {r.content for r in ns.records} == {
        "ns1.example.com.",
        "ns2.example.com.",
    }
    www_a = by_name_type[("www.example.com.", "A")]
    assert {r.content for r in www_a.records} == {"10.0.0.1", "10.0.0.2"}
    assert www_a.ttl == 3600
    mx = by_name_type[("mail.example.com.", "MX")]
    assert mx.records[0].content == "10 mx.example.com."


def test_from_zonefile_invalid_rejected(tmp_path: Path) -> None:
    zf = tmp_path / "broken.zone"
    zf.write_text("this is not a zone file, just prose.\n")
    with pytest.raises(ValidationError) as exc:
        from_zonefile(zf, zone="example.com")
    assert "parse" in exc.value.message.lower() or "zone" in exc.value.message.lower()


def test_from_zonefile_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        from_zonefile(tmp_path / "nope.zone", zone="example.com")

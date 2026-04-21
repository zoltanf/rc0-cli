"""BIND zone-file renderer used by ``rc0 record export -f bind``."""

from __future__ import annotations

import io
from typing import Any

import dns.name
import dns.rdata
import dns.rdataclass
import dns.rdataset
import dns.rdatatype
import dns.zone


def render_rrsets(*, zone: str, rrsets: list[dict[str, Any]]) -> str:
    """Render ``rrsets`` as a BIND-format zone file for ``zone``.

    Disabled records are skipped. The ``$ORIGIN`` directive is emitted.
    """
    origin = dns.name.from_text(zone.rstrip(".") + ".")
    z = dns.zone.Zone(origin=origin)
    for rr in rrsets:
        name = dns.name.from_text(rr["name"])
        rdtype = dns.rdatatype.from_text(rr["type"])
        ttl = int(rr.get("ttl", 3600))
        node = z.find_node(name, create=True)
        rdataset = node.find_rdataset(dns.rdataclass.IN, rdtype, create=True)
        rdataset.ttl = ttl
        for rec in rr.get("records", []):
            if rec.get("disabled"):
                continue
            rdata = dns.rdata.from_text(dns.rdataclass.IN, rdtype, rec["content"])
            rdataset.add(rdata)
    buf = io.StringIO()
    z.to_file(buf, relativize=False)
    return f"$ORIGIN {origin.to_text()}\n{buf.getvalue()}"

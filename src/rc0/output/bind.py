"""BIND zone-file renderer used by ``rc0 record export -f bind``."""

from __future__ import annotations

import io
import sys
from typing import Any

import dns.exception
import dns.name
import dns.rdata
import dns.rdataclass
import dns.rdataset
import dns.rdatatype
import dns.zone
from dns.rdtypes.ANY.SPF import SPF
from dns.rdtypes.ANY.TXT import TXT

_TXT_CHUNK_LIMIT = 255  # RFC 1035 §3.3.14: each TXT character-string is ≤255 bytes.


def render_rrsets(*, zone: str, rrsets: list[dict[str, Any]]) -> str:
    """Render ``rrsets`` as a BIND-format zone file for ``zone``.

    Disabled records are skipped. The ``$ORIGIN`` directive is emitted.

    TXT and SPF records are chunked into RFC 1035 §3.3.14 ≤255-byte segments
    so that long entries (e.g. 2048-bit DKIM keys) survive the round-trip
    instead of crashing dnspython's ``from_text`` on the full string.
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
            rdata: dns.rdata.Rdata
            try:
                if rdtype in (dns.rdatatype.TXT, dns.rdatatype.SPF):
                    rdata = _build_txt_rdata(dns.rdataclass.IN, rdtype, rec["content"])
                else:
                    rdata = dns.rdata.from_text(dns.rdataclass.IN, rdtype, rec["content"])
            except (dns.exception.DNSException, ValueError, SyntaxError) as exc:
                print(
                    f"warning: skipped record at {rr['name']} ({rr['type']}): {exc}",
                    file=sys.stderr,
                )
                continue
            rdataset.add(rdata)
    buf = io.StringIO()
    z.to_file(buf, relativize=False)
    return f"$ORIGIN {origin.to_text()}\n{buf.getvalue()}"


def _build_txt_rdata(
    rdclass: dns.rdataclass.RdataClass,
    rdtype: dns.rdatatype.RdataType,
    content: str,
) -> TXT | SPF:
    """Construct a TXT/SPF rdata, re-chunking strings to ≤255 bytes.

    The RcodeZero API returns long TXT content as one quoted string. dnspython's
    ``from_text`` rejects any single quoted string >255 bytes, so we parse the
    content ourselves and split each underlying byte string into ≤255-byte
    chunks before handing it to the rdata constructor (which holds the strings
    as a list of bytes, no length check).
    """
    parsed = _parse_txt_content(content)
    if not parsed:
        parsed = [b""]
    chunks: list[bytes] = []
    for raw in parsed:
        chunks.extend(_chunk_bytes(raw))
    if rdtype == dns.rdatatype.SPF:
        return SPF(rdclass, rdtype, chunks)
    return TXT(rdclass, rdtype, chunks)


def _chunk_bytes(s: bytes, *, limit: int = _TXT_CHUNK_LIMIT) -> list[bytes]:
    if not s:
        return [b""]
    return [s[i : i + limit] for i in range(0, len(s), limit)]


def _parse_txt_content(content: str) -> list[bytes]:
    """Parse a TXT rdata content string into its character-string segments.

    Accepts:
      ``"part1" "part2"`` → ``[b"part1", b"part2"]``
      ``"single string"`` → ``[b"single string"]``
      bare atom (no quotes) → one segment
    Handles ``\\"``, ``\\\\``, and ``\\DDD`` decimal escapes inside quotes —
    matching dnspython's tokenizer rules. Does not enforce the per-segment
    255-byte limit; callers re-chunk afterwards.
    """
    out: list[bytes] = []
    i = 0
    n = len(content)
    while i < n:
        ch = content[i]
        if ch.isspace():
            i += 1
            continue
        if ch == '"':
            i += 1
            buf = bytearray()
            while i < n:
                c = content[i]
                if c == "\\" and i + 1 < n:
                    nxt = content[i + 1]
                    if (
                        nxt.isdigit()
                        and i + 3 < n
                        and content[i + 2].isdigit()
                        and content[i + 3].isdigit()
                    ):
                        buf.append(int(content[i + 1 : i + 4]))
                        i += 4
                        continue
                    buf.append(ord(nxt))
                    i += 2
                    continue
                if c == '"':
                    i += 1
                    break
                buf.extend(c.encode("utf-8"))
                i += 1
            out.append(bytes(buf))
        else:
            j = i
            while j < n and not content[j].isspace():
                j += 1
            out.append(content[i:j].encode("utf-8"))
            i = j
    return out

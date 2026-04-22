#!/usr/bin/env python3
"""Generate docs/api-coverage.md from the pinned OpenAPI spec and CLI mapping.

Run from the repo root:
    uv run python scripts/gen_api_coverage.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SPEC_PATH = REPO_ROOT / "tests" / "fixtures" / "openapi.json"
OUT_PATH = REPO_ROOT / "docs" / "api-coverage.md"

# Full endpoint → CLI command mapping (extends contract test map with mutations)
ENDPOINT_TO_COMMAND: dict[tuple[str, str], tuple[str, ...]] = {
    # ACME (v1)
    ("GET", "/api/v1/acme/{zone}"): ("acme", "zone-exists"),
    ("GET", "/api/v1/acme/zones/{zone}/rrsets"): ("acme", "list-challenges"),
    ("PATCH", "/api/v1/acme/zones/{zone}/rrsets"): ("acme", "add-challenge / remove-challenge"),
    # Messages
    ("GET", "/api/v2/messages"): ("messages", "poll"),
    ("GET", "/api/v2/messages/list"): ("messages", "list"),
    ("DELETE", "/api/v2/messages/{id}"): ("messages", "ack"),
    # Reports
    ("GET", "/api/v2/reports/accounting"): ("report", "accounting"),
    ("GET", "/api/v2/reports/domainlist"): ("report", "domainlist"),
    ("GET", "/api/v2/reports/nxdomains"): ("report", "nxdomains"),
    ("GET", "/api/v2/reports/problematiczones"): ("report", "problematic-zones"),
    ("GET", "/api/v2/reports/queryrates"): ("report", "queryrates"),
    # Settings
    ("GET", "/api/v2/settings"): ("settings", "show"),
    ("PUT", "/api/v2/settings/secondaries"): ("settings", "secondaries", "set"),
    ("DELETE", "/api/v2/settings/secondaries"): ("settings", "secondaries", "unset"),
    ("PUT", "/api/v2/settings/tsig/in"): ("settings", "tsig-in", "set"),
    ("DELETE", "/api/v2/settings/tsig/in"): ("settings", "tsig-in", "unset"),
    ("PUT", "/api/v2/settings/tsig/out"): ("settings", "tsig-out", "set"),
    ("DELETE", "/api/v2/settings/tsig/out"): ("settings", "tsig-out", "unset"),
    ("PUT", "/api/v2/settings/tsigout"): ("[DEPRECATED — no CLI command]",),
    ("DELETE", "/api/v2/settings/tsigout"): ("[DEPRECATED — no CLI command]",),
    # Stats
    ("GET", "/api/v2/stats/countries"): ("stats", "countries"),
    ("GET", "/api/v2/stats/querycounts"): ("stats", "queries"),
    ("GET", "/api/v2/stats/topmagnitude"): ("stats", "topmagnitude"),
    ("GET", "/api/v2/stats/topnxdomains"): ("stats", "topnxdomains"),
    ("GET", "/api/v2/stats/topqnames"): ("stats", "topqnames"),
    ("GET", "/api/v2/stats/topzones"): ("stats", "topzones"),
    # TSIG
    ("GET", "/api/v2/tsig"): ("tsig", "list"),
    ("POST", "/api/v2/tsig"): ("tsig", "add"),
    ("GET", "/api/v2/tsig/out"): ("tsig", "list-out"),
    ("POST", "/api/v2/tsig/out"): ("[DEPRECATED — no CLI command]",),
    ("PUT", "/api/v2/tsig/out/{keyname}"): ("[DEPRECATED — no CLI command]",),
    ("DELETE", "/api/v2/tsig/out/{keyname}"): ("[DEPRECATED — no CLI command]",),
    ("GET", "/api/v2/tsig/{keyname}"): ("tsig", "show"),
    ("PUT", "/api/v2/tsig/{keyname}"): ("tsig", "update"),
    ("DELETE", "/api/v2/tsig/{keyname}"): ("tsig", "delete"),
    # Zones
    ("GET", "/api/v2/zones"): ("zone", "list"),
    ("POST", "/api/v2/zones"): ("zone", "create"),
    ("GET", "/api/v2/zones/{zone}"): ("zone", "show"),
    ("PUT", "/api/v2/zones/{zone}"): ("zone", "update"),
    ("PATCH", "/api/v2/zones/{zone}"): ("zone", "enable / disable"),
    ("DELETE", "/api/v2/zones/{zone}"): ("zone", "delete"),
    ("GET", "/api/v2/zones/{zone}/inbound"): ("zone", "xfr-in", "show"),
    ("POST", "/api/v2/zones/{zone}/inbound"): ("zone", "xfr-in", "set"),
    ("DELETE", "/api/v2/zones/{zone}/inbound"): ("zone", "xfr-in", "unset"),
    ("POST", "/api/v2/zones/{zone}/keyrollover"): ("dnssec", "keyrollover"),
    ("GET", "/api/v2/zones/{zone}/outbound"): ("zone", "xfr-out", "show"),
    ("POST", "/api/v2/zones/{zone}/outbound"): ("zone", "xfr-out", "set"),
    ("DELETE", "/api/v2/zones/{zone}/outbound"): ("zone", "xfr-out", "unset"),
    ("GET", "/api/v2/zones/{zone}/rrsets"): ("record", "list"),
    ("PATCH", "/api/v2/zones/{zone}/rrsets"): ("record", "add / update / delete / apply"),
    ("PUT", "/api/v2/zones/{zone}/rrsets"): ("record", "replace-all"),
    ("DELETE", "/api/v2/zones/{zone}/rrsets"): ("record", "clear"),
    ("POST", "/api/v2/zones/{zone}/retrieve"): ("zone", "retrieve"),
    ("POST", "/api/v2/zones/{zone}/sign"): ("dnssec", "sign"),
    ("GET", "/api/v2/zones/{zone}/simulate/dsremoved"): ("dnssec", "simulate", "dsremoved"),
    ("POST", "/api/v2/zones/{zone}/simulate/dsremoved"): ("dnssec", "simulate", "dsremoved"),
    ("GET", "/api/v2/zones/{zone}/simulate/dsseen"): ("dnssec", "simulate", "dsseen"),
    ("POST", "/api/v2/zones/{zone}/simulate/dsseen"): ("dnssec", "simulate", "dsseen"),
    ("GET", "/api/v2/zones/{zone}/stats/magnitude"): ("stats", "zone", "magnitude"),
    ("GET", "/api/v2/zones/{zone}/stats/nxdomains"): ("stats", "zone", "nxdomains"),
    ("GET", "/api/v2/zones/{zone}/stats/qnames"): ("stats", "zone", "qnames"),
    ("GET", "/api/v2/zones/{zone}/stats/queries"): ("stats", "zone", "queries"),
    ("GET", "/api/v2/zones/{zone}/status"): ("zone", "status"),
    ("POST", "/api/v2/zones/{zone}/unsign"): ("dnssec", "unsign"),
    ("POST", "/api/v2/zones/{zone}/dsupdate"): ("dnssec", "ack-ds"),
}


def main() -> int:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    spec_version = spec.get("info", {}).get("version", "unknown")

    rows: list[tuple[str, str, bool, str, str]] = []  # (method, path, deprecated, command, status)
    unmapped: list[tuple[str, str]] = []

    method_order = {"get": 0, "post": 1, "put": 2, "patch": 3, "delete": 4}

    for path, path_item in sorted(spec["paths"].items()):
        for method in sorted(path_item.keys(), key=lambda m: method_order.get(m, 99)):
            if method not in method_order:
                continue
            op = path_item[method]
            deprecated = op.get("deprecated", False)
            key = (method.upper(), path)
            cmd = ENDPOINT_TO_COMMAND.get(key)
            if cmd is None:
                unmapped.append(key)
                rows.append((method.upper(), path, deprecated, "", "❌"))
            elif cmd[0].startswith("[DEPRECATED"):
                rows.append((method.upper(), path, deprecated, cmd[0], "⚠️"))
            else:
                cmd_str = "rc0 " + " ".join(cmd)
                rows.append((method.upper(), path, deprecated, cmd_str, "✅"))

    lines: list[str] = [
        "# API Coverage",
        "",
        f"Generated from pinned OpenAPI spec v{spec_version}.",
        "",
        "| Status | Method | Endpoint | CLI Command | Notes |",
        "|--------|--------|----------|-------------|-------|",
    ]
    for method, path, deprecated, cmd, status in rows:
        dep_note = "[DEPRECATED]" if deprecated else ""
        lines.append(f"| {status} | `{method}` | `{path}` | `{cmd}` | {dep_note} |")

    if unmapped:
        lines += ["", "## Unmapped endpoints", ""]
        for method, path in unmapped:
            lines.append(f"- `{method} {path}`")

    lines.append("")
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    mapped = sum(1 for r in rows if r[4] == "✅")
    total = len(rows)
    print(f"Generated {OUT_PATH} — {mapped}/{total} endpoints mapped.")
    if unmapped:
        print(f"WARNING: {len(unmapped)} unmapped endpoints:", file=sys.stderr)
        for m, p in unmapped:
            print(f"  {m} {p}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Map of v2 GET endpoints → CLI command path for the contract test.

Whenever ``scripts/update-openapi.sh`` bumps the pinned spec and a new
endpoint appears, add a mapping here. The test fails loudly if a spec
endpoint is not represented.
"""

from __future__ import annotations

V2_GET_TO_COMMAND: dict[str, tuple[str, ...]] = {
    "/api/v2/zones": ("zone", "list"),
    "/api/v2/zones/{zone}": ("zone", "show"),
    "/api/v2/zones/{zone}/status": ("zone", "status"),
    "/api/v2/zones/{zone}/rrsets": ("record", "list"),
    "/api/v2/zones/{zone}/inbound": ("zone", "xfr-in", "show"),  # Phase 2
    "/api/v2/zones/{zone}/outbound": ("zone", "xfr-out", "show"),  # Phase 2
    "/api/v2/tsig": ("tsig", "list"),
    "/api/v2/tsig/{keyname}": ("tsig", "show"),
    "/api/v2/tsig/out": ("tsig", "list-out"),
    "/api/v2/settings": ("settings", "show"),
    "/api/v2/messages": ("messages", "poll"),
    "/api/v2/messages/list": ("messages", "list"),
    "/api/v2/stats/querycounts": ("stats", "queries"),
    "/api/v2/stats/topzones": ("stats", "topzones"),
    "/api/v2/stats/countries": ("stats", "countries"),
    "/api/v2/stats/topmagnitude": ("stats", "topmagnitude"),
    "/api/v2/stats/topnxdomains": ("stats", "topnxdomains"),
    "/api/v2/stats/topqnames": ("stats", "topqnames"),
    "/api/v2/zones/{zone}/stats/queries": ("stats", "zone", "queries"),
    "/api/v2/zones/{zone}/stats/magnitude": ("stats", "zone", "magnitude"),
    "/api/v2/zones/{zone}/stats/nxdomains": ("stats", "zone", "nxdomains"),
    "/api/v2/zones/{zone}/stats/qnames": ("stats", "zone", "qnames"),
    "/api/v2/reports/problematiczones": ("report", "problematic-zones"),
    "/api/v2/reports/nxdomains": ("report", "nxdomains"),
    "/api/v2/reports/accounting": ("report", "accounting"),
    "/api/v2/reports/queryrates": ("report", "queryrates"),
    "/api/v2/reports/domainlist": ("report", "domainlist"),
}

# Paths that the contract test tolerates as "mapped but not yet implemented".
# Remove entries here as later phases land the commands.
PHASE_2_OR_LATER: frozenset[str] = frozenset(
    {
        "/api/v2/zones/{zone}/inbound",
        "/api/v2/zones/{zone}/outbound",
    },
)

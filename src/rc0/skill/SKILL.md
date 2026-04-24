---
name: rc0
description: Use when the user wants to manage DNS zones or records via rcodezero, check DNS traffic stats, view NXDOMAIN reports, or do anything with the rc0 CLI tool.
---

# rc0 — RcodeZero DNS CLI

Binary: `rc0`

When unsure about a command: `rc0 <resource> <verb> --help` — all commands have examples in help.

## Zones

```bash
rc0 zone list
rc0 zone create <domain>               # MASTER by default
rc0 zone delete <domain>               # prompts confirmation; use -y to skip
```

## Records

```bash
rc0 record add <zone> --name <name> --type <type> --content <value>
# --name @ for apex; repeat --content for multiple values in one RRset
# MX content format: "10 mail.example.com."  (priority + FQDN with trailing dot)
# ALIAS content must differ from the zone apex itself
```

## Stats & Reports

```bash
rc0 stats topzones                            # all zones ranked by traffic
rc0 stats queries                             # account-wide query counts per day (2 cols: total, nxdomain)
rc0 stats zone queries <zone>                 # per-zone daily counts (same 2-col format)
rc0 report nxdomains                          # today's NXDOMAIN hits, all zones
rc0 report nxdomains --day yesterday
rc0 report queryrates                         # per-zone query rates
```

`stats queries` output columns: `date total_queries nxdomain_queries` (no headers in output).

`report nxdomains` only supports `today` / `yesterday` — no historical date range.

## Safety

- Always confirm with the user before `zone delete` or `record add` without `--append` on an apex TXT (overwrites the whole RRset).
- Use `--dry-run` to preview any mutation without executing.

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
rc0 record set <zone> --name <name> --type <type> --content <value>
# Default = upsert: works whether the RRset exists or not.
# Add --require-absent to refuse when one already exists (strict create).
# Add --require-exists to refuse when none exists (strict replace).
# --name @ for apex; repeat --content for multiple values in one RRset.
# MX content format: "10 mail.example.com."  (priority + FQDN with trailing dot)
# ALIAS content must differ from the zone apex itself

rc0 record append <zone> --name <name> --type <type> --content <value>
# Non-destructive: fetches the current RRset, dedupes, writes the merged set.
# Use this for SPF includes, extra MX hosts, additional TXT verification tokens.

rc0 record delete <zone> --name <name> --type <type>
# Prompts y/N. Pass -y to skip.

rc0 record import <zone> --zone-file <bind-file>
# Full zone replacement. Anything not in the input disappears.
# Prompts for typed-zone confirmation. Pass -y to skip.
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

- Always confirm with the user before `zone delete`, `record import`, `record clear`, or any `record set` on an apex TXT/SPF/MX (a bare `record set` replaces the entire RRset). When the goal is to keep existing records, prefer `record append`.
- Use `--dry-run` to preview any mutation without executing.

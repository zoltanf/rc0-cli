# Mission Plan: `rc0` — Command-Line Interface for RcodeZero Anycast DNS

> **Agent brief.** You are implementing a production-grade, first-class CLI for the [RcodeZero Anycast DNS API](https://my.rcodezero.at/openapi/) (v2, plus the v1 ACME endpoints). The tool must cover **every non-internal endpoint**, feel like `gh` / `az` / `kubectl` to use, be safe-by-default for destructive operations (dry-run, confirmations), and be equally usable by humans at a terminal and by LLM agents via stdin/stdout contract.
>
> This document is the single source of truth. Follow it end-to-end. Where a decision is not specified here, the rule is: **mirror `gh`'s UX conventions, output JSON cleanly, fail loud, fail fast, never surprise the user**.

---

## 1. The name: `rc0`

**Binary name:** `rc0`
**PyPI package name:** `rc0-cli`
**Homebrew formula name:** `rc0`
**GitHub repo:** `rc0-cli` (organisation owner's choice)

### Why `rc0`

- **Brand-aligned.** RcodeZero refers to itself as "rcode0" and uses `rc0` as its internal short form: the official Go library is [`rc0go`](https://github.com/nic-at/rc0go), the ExternalDNS env var is `RC0_API_KEY`, the certbot plugin flag is `--dns-rcode0`. Anyone who's touched their ecosystem already types "rc0".
- **Short and sticky.** Three characters, like `gh`, `az`, `aws`. Tab-completion-friendly. No vowel nightmares. Fits in shell prompts and docs.
- **Self-describing in context.** For anyone who knows the DNS provider, the name says "this is the rcode0 CLI". For anyone who doesn't, `rc0 --help` tells them on line one: *"Command-line interface for RcodeZero Anycast DNS."*
- **No collisions.** No PyPI package named `rc0-cli` exists. No Homebrew formula named `rc0` exists. The GitHub identifier `rc0-cli` is free at time of writing.

**Tagline (use in README, `--help`, package metadata):** *"The command line for RcodeZero DNS."*

---

## 2. Goals and non-goals

### Goals

1. **Complete API coverage.** Every non-deprecated endpoint in `rcode0api-v2.json` is reachable as a CLI command. Deprecated endpoints are still reachable but marked `[deprecated]` in help and hidden from the default command listing.
2. **Two first-class users: humans and agents.** Every command works well in an interactive terminal AND is scriptable/parseable via structured output.
3. **Safety by default for mutations.** Any command that changes state supports `--dry-run`. High-risk commands (zone delete, rrset replace, DNSSEC unsign, force flags) require explicit confirmation unless `--yes` / `-y` is passed.
4. **Inline help that doubles as documentation.** Help text explains *what the command does*, *what the API does under the hood*, *example usage*, and *common pitfalls*. Agents reading `--help` should have enough to call the command correctly without external docs.
5. **Ship as a binary.** Single-file binary per platform, installable via Homebrew on macOS, via GitHub Releases on Linux/Windows, and via `pip install rc0-cli` / `uv tool install rc0-cli` from PyPI.

### Non-goals

- Not a DNS resolver, zone file parser, or DNSSEC validator. The CLI is a thin, typed layer over the HTTP API plus ergonomics.
- Not a TUI. No curses, no interactive menus (except confirmation prompts).
- Not a state store. The CLI is stateless except for config (API token, default output format, etc.).

---

## 3. Technology stack

| Concern | Choice | Why |
|---|---|---|
| Language | Python **3.14** (3.14.4+) | User requirement; latest stable. |
| CLI framework | **Typer** (≥0.15) | Type-hint-driven, auto-generated help, clean autocompletion, Click under the hood. |
| HTTP client | **httpx** (≥0.28) | Modern, HTTP/2, sync+async, timeouts done right. |
| Data models | **Pydantic v2** | Request/response validation, schema export for agents. |
| Terminal output | **Rich** | Tables, JSON/YAML pretty-printing, progress bars, colored errors. |
| Config | **pydantic-settings** v2 | Layered config (CLI flag > env var > config file > default). |
| Packaging | **uv** + `pyproject.toml` | Fast, reproducible builds. `uv build` for wheels. |
| Binary | **PyInstaller** (onefile) with platform matrix, **or** Nuitka if size becomes a concern | Mature, cross-platform, produces single-file executables. |
| Tests | **pytest**, **respx** (httpx mock), **pytest-snapshot** for CLI output | Standard. |
| Linting/formatting | **ruff** (lint + format) | One tool, fast. |
| Type checking | **mypy --strict** | Required. |
| CI | GitHub Actions | Matrix: macOS-14 (arm64), macOS-13 (x86_64), ubuntu-24.04 (x86_64), ubuntu-24.04-arm (arm64), windows-2025 (x86_64). |
| Release signing | `cosign` + SLSA provenance (optional v1.1) | Supply chain hygiene. |

---

## 4. API reference summary

**Base URL:** `https://my.rcodezero.at`
**Auth:** HTTP Bearer token in `Authorization: Bearer <token>`
**OpenAPI spec:** `https://my.rcodezero.at/openapi/rcode0api-v2.json`
**Current API version:** 2.9

### Endpoint inventory

The CLI must expose **all** of the following. Endpoints marked `[DEPRECATED]` are still implemented but hidden from default `--help` listings and emit a stderr warning when invoked.

#### Zone Management (`/api/v2/zones`)

| Endpoint | Method | Command |
|---|---|---|
| `/api/v2/zones` | GET | `rc0 zone list` |
| `/api/v2/zones` | POST | `rc0 zone create` |
| `/api/v2/zones/{zone}` | GET | `rc0 zone show` |
| `/api/v2/zones/{zone}` | PUT | `rc0 zone update` |
| `/api/v2/zones/{zone}` | PATCH | `rc0 zone enable` / `rc0 zone disable` |
| `/api/v2/zones/{zone}` | DELETE | `rc0 zone delete` |
| `/api/v2/zones/{zone}/rrsets` | GET | `rc0 record list` |
| `/api/v2/zones/{zone}/rrsets` | PATCH | `rc0 record set` / `append` / `delete` / `apply` |
| `/api/v2/zones/{zone}/rrsets` | PUT | `rc0 record import` |
| `/api/v2/zones/{zone}/rrsets` | DELETE | `rc0 record clear` |
| `/api/v2/zones/{zone}/retrieve` | POST | `rc0 zone retrieve` |
| `/api/v2/zones/{zone}/outbound` | GET/POST/DELETE | `rc0 zone xfr-out show/set/unset` |
| `/api/v2/zones/{zone}/inbound` | GET/POST/DELETE | `rc0 zone xfr-in show/set/unset` |
| `/api/v2/zones/{zone}/status` | GET | `rc0 zone status` |
| `/api/v2/zones/{zone}/sign` | POST | `rc0 dnssec sign` |
| `/api/v2/zones/{zone}/unsign` | POST | `rc0 dnssec unsign` |
| `/api/v2/zones/{zone}/keyrollover` | POST | `rc0 dnssec keyrollover` |
| `/api/v2/zones/{zone}/dsupdate` | POST | `rc0 dnssec ack-ds` |
| `/api/v2/zones/{zone}/simulate/dsseen` | POST | `rc0 dnssec simulate dsseen` (test env only) |
| `/api/v2/zones/{zone}/simulate/dsremoved` | POST | `rc0 dnssec simulate dsremoved` (test env only) |

#### TSIG Keys (`/api/v2/tsig`)

| Endpoint | Method | Command |
|---|---|---|
| `/api/v2/tsig` | GET | `rc0 tsig list` |
| `/api/v2/tsig` | POST | `rc0 tsig add` |
| `/api/v2/tsig/{keyname}` | GET | `rc0 tsig show` |
| `/api/v2/tsig/{keyname}` | PUT | `rc0 tsig update` |
| `/api/v2/tsig/{keyname}` | DELETE | `rc0 tsig delete` |
| `/api/v2/tsig/out` | GET | `rc0 tsig list-out` **[DEPRECATED]** |
| `/api/v2/tsig/out` | POST | `rc0 tsig add-out` **[DEPRECATED]** |
| `/api/v2/tsig/out/{keyname}` | PUT | `rc0 tsig update-out` **[DEPRECATED]** |
| `/api/v2/tsig/out/{keyname}` | DELETE | `rc0 tsig delete-out` **[DEPRECATED]** |

#### Zone Statistics (`/api/v2/zones/{zone}/stats`)

| Endpoint | Command |
|---|---|
| `/api/v2/zones/{zone}/stats/queries` | `rc0 stats zone queries` |
| `/api/v2/zones/{zone}/stats/magnitude` | `rc0 stats zone magnitude` **[DEPRECATED]** |
| `/api/v2/zones/{zone}/stats/qnames` | `rc0 stats zone qnames` **[DEPRECATED]** |
| `/api/v2/zones/{zone}/stats/nxdomains` | `rc0 stats zone nxdomains` **[DEPRECATED]** |

#### Account Statistics (`/api/v2/stats`)

| Endpoint | Command |
|---|---|
| `/api/v2/stats/topzones` | `rc0 stats topzones` |
| `/api/v2/stats/querycounts` | `rc0 stats queries` |
| `/api/v2/stats/countries` | `rc0 stats countries` |
| `/api/v2/stats/topqnames` | `rc0 stats topqnames` **[DEPRECATED]** |
| `/api/v2/stats/topnxdomains` | `rc0 stats topnxdomains` **[DEPRECATED]** |
| `/api/v2/stats/topmagnitude` | `rc0 stats topmagnitude` **[DEPRECATED]** |

#### Message Queue (`/api/v2/messages`)

| Endpoint | Command |
|---|---|
| `/api/v2/messages` | `rc0 messages poll` |
| `/api/v2/messages/list` | `rc0 messages list` |
| `/api/v2/messages/{id}` DELETE | `rc0 messages ack <id>` |

#### Account Settings (`/api/v2/settings`)

| Endpoint | Command |
|---|---|
| `/api/v2/settings` GET | `rc0 settings show` |
| `/api/v2/settings/secondaries` PUT/DELETE | `rc0 settings secondaries set/unset` |
| `/api/v2/settings/tsig/in` PUT/DELETE | `rc0 settings tsig-in set/unset` |
| `/api/v2/settings/tsig/out` PUT/DELETE | `rc0 settings tsig-out set/unset` |
| `/api/v2/settings/tsigout` PUT/DELETE | `rc0 settings tsigout-legacy set/unset` **[DEPRECATED]** |

#### Reports (`/api/v2/reports`)

| Endpoint | Command |
|---|---|
| `/api/v2/reports/problematiczones` | `rc0 report problematic-zones` |
| `/api/v2/reports/nxdomains` | `rc0 report nxdomains` |
| `/api/v2/reports/accounting` | `rc0 report accounting` |
| `/api/v2/reports/queryrates` | `rc0 report queryrates` |
| `/api/v2/reports/domainlist` | `rc0 report domainlist` |

#### ACME (`/api/v1/acme`) — v1 endpoints, still current

| Endpoint | Command |
|---|---|
| `/api/v1/acme/{zone}` GET | `rc0 acme zone-exists` |
| `/api/v1/acme/zones/{zone}/rrsets` GET | `rc0 acme list-challenges` |
| `/api/v1/acme/zones/{zone}/rrsets` PATCH | `rc0 acme add-challenge` / `rc0 acme remove-challenge` |

Auth note: ACME endpoints accept only tokens with the `ACME` permission. If a call returns 403, the error message must explicitly tell the user to check that their token has the ACME permission.

---

## 5. Command tree (final)

```
rc0
├── auth
│   ├── login               # Interactive: prompts for token, validates, saves to config
│   ├── logout              # Removes stored token
│   ├── status              # Shows "Authenticated as: ... using token ending in XXXX"
│   └── whoami              # Alias for status
├── config
│   ├── show                # Prints effective config + source of each value
│   ├── get <key>           # e.g. `rc0 config get output_format`
│   ├── set <key> <value>   # e.g. `rc0 config set output_format json`
│   ├── unset <key>
│   └── path                # Prints the config file path
├── zone
│   ├── list                # GET /zones (paginated, with --all to auto-page)
│   ├── show <zone>         # GET /zones/{zone}
│   ├── create <domain>     # POST /zones  (--type master|slave, --master IP ...)
│   ├── update <zone>       # PUT /zones/{zone}
│   ├── delete <zone>       # DELETE /zones/{zone}  [CONFIRMATION]
│   ├── enable <zone>       # PATCH zone_disabled=false
│   ├── disable <zone>      # PATCH zone_disabled=true
│   ├── status <zone>       # GET /zones/{zone}/status
│   ├── retrieve <zone>     # POST /zones/{zone}/retrieve
│   ├── test <domain>       # POST /zones?test=1 — validates without creating
│   ├── xfr-in
│   │   ├── show <zone>
│   │   ├── set <zone>      # --tsigkey NAME
│   │   └── unset <zone>
│   └── xfr-out
│       ├── show <zone>
│       ├── set <zone>      # --secondary IP ... --tsigkey NAME
│       └── unset <zone>
├── record
│   ├── list <zone>         # GET /zones/{zone}/rrsets  (--name, --type)
│   ├── add <zone>          # PATCH with changetype=add
│   ├── update <zone>       # PATCH with changetype=update
│   ├── delete <zone>       # PATCH with changetype=delete  [CONFIRMATION if prod]
│   ├── apply <zone>        # PATCH from a JSON/YAML file (--from-file)  [CONFIRMATION]
│   ├── replace-all <zone>  # PUT  (full zone replacement — zone-transfer semantics)  [CONFIRMATION]
│   ├── clear <zone>        # DELETE all rrsets except SOA/NS  [CONFIRMATION]
│   └── export <zone>       # GET all rrsets as BIND zone file, JSON, or YAML
├── dnssec
│   ├── sign <zone>         # POST /zones/{zone}/sign
│   │                       # --ignore-safety-period  --enable-cds-cdnskey
│   ├── unsign <zone>       # POST /zones/{zone}/unsign  [CONFIRMATION]  --force
│   ├── keyrollover <zone>  # POST /zones/{zone}/keyrollover  [CONFIRMATION]
│   ├── ack-ds <zone>       # POST /zones/{zone}/dsupdate
│   └── simulate            # Test-system only
│       ├── dsseen <zone>
│       └── dsremoved <zone>
├── tsig
│   ├── list
│   ├── show <name>
│   ├── add <name>          # --algorithm hmac-sha256 --secret BASE64  (or --generate)
│   ├── update <name>
│   └── delete <name>       # [CONFIRMATION]
├── messages
│   ├── poll                # GET /messages — oldest unacknowledged
│   ├── list                # GET /messages/list (paginated, filterable)
│   ├── ack <id>            # DELETE /messages/{id}
│   └── ack-all             # Loop: poll + ack until empty  [CONFIRMATION]
├── settings
│   ├── show                # GET /settings
│   ├── secondaries
│   │   ├── set             # --ip 1.2.3.4 --ip ...
│   │   └── unset
│   ├── tsig-in
│   │   ├── set <tsigkey>
│   │   └── unset
│   └── tsig-out
│       ├── set <tsigkey>
│       └── unset
├── stats
│   ├── queries             # account-wide  /stats/querycounts
│   ├── topzones            # /stats/topzones
│   ├── countries           # /stats/countries
│   └── zone
│       └── queries <zone>  # /zones/{zone}/stats/queries
├── report
│   ├── problematic-zones
│   ├── nxdomains           # --day today|yesterday  --format csv|json
│   ├── accounting          # --month YYYY-MM  --format csv|json
│   ├── queryrates          # --month YYYY-MM | --day YYYY-MM-DD  --include-nx
│   └── domainlist
├── acme
│   ├── zone-exists <zone>
│   ├── list-challenges <zone>
│   ├── add-challenge <zone> --value TOKEN [--ttl 60]
│   └── remove-challenge <zone>
├── help <topic>            # Deep-dive topics: "dnssec-workflow", "rrset-format",
│                           #   "dry-run", "output-formats", "authentication", "exit-codes"
├── completion              # Shell completion: bash, zsh, fish, powershell
├── introspect              # Outputs full JSON schema of all commands (for agents)
└── version                 # Prints version, commit, Python version, platform
```

---

## 6. Global flags

Every command accepts these:

| Flag | Env var | Default | Purpose |
|---|---|---|---|
| `--token TOKEN` | `RC0_API_TOKEN` | from config | API bearer token |
| `--api-url URL` | `RC0_API_URL` | `https://my.rcodezero.at` | Base URL (for test env) |
| `--output FMT`, `-o FMT` | `RC0_OUTPUT` | `table` | One of `table`, `json`, `yaml`, `csv`, `tsv`, `plain` |
| `--jq EXPR` | — | — | Applies a jq expression to JSON output (when `-o json`) |
| `--dry-run` | `RC0_DRY_RUN` | false | For mutations: don't perform the call; emit the intended request |
| `--yes`, `-y` | `RC0_YES` | false | Skip confirmation prompts |
| `--no-color` | `NO_COLOR` | auto-detect TTY | Disable ANSI colors |
| `--quiet`, `-q` | — | false | Suppress non-essential output |
| `--verbose`, `-v` | `RC0_VERBOSE` | 0 | Increase log verbosity (repeatable: `-vv`) |
| `--log-file PATH` | `RC0_LOG_FILE` | — | Also write logs to a file (always JSON lines) |
| `--timeout SECONDS` | `RC0_TIMEOUT` | `30` | HTTP timeout |
| `--retries N` | `RC0_RETRIES` | `3` | Retry idempotent GET calls on 5xx/timeout |
| `--config PATH` | `RC0_CONFIG` | see §8 | Explicit config file |
| `--profile NAME` | `RC0_PROFILE` | `default` | Select a named profile in config |
| `--help`, `-h` | — | — | Help at every command level |
| `--version` | — | — | Print version and exit |

**Precedence:** command-line flag > environment variable > profile in config file > global default.

---

## 7. The dry-run contract (critical)

Every state-changing command **must** support `--dry-run`. Dry-run produces no HTTP mutation and exits 0.

### Dry-run output

- **Human mode (`-o table`, default):** a framed "Would execute" block showing method, URL, headers (with token redacted), and body (prettified JSON). Plus an English summary: *"Would create zone example.com as master with 2 master IPs."*
- **Machine mode (`-o json`):**
  ```json
  {
    "dry_run": true,
    "request": {
      "method": "POST",
      "url": "https://my.rcodezero.at/api/v2/zones",
      "headers": { "Authorization": "Bearer ***REDACTED***", "Content-Type": "application/json" },
      "body": { "domain": "example.com", "type": "master" }
    },
    "summary": "Would create zone example.com as master with 2 master IPs.",
    "side_effects": ["creates_zone", "may_create_dnssec_keys"]
  }
  ```

### `--dry-run` vs. the API's own `test=1` query param

The `POST /api/v2/zones?test=1` endpoint is different: it's a server-side validation call. Expose it as `rc0 zone test <domain>`. Do **not** conflate it with `--dry-run`. `--dry-run` never contacts the API; `zone test` does.

### Commands that require confirmation by default (prompt unless `-y` or `--dry-run`)

- `rc0 zone delete`
- `rc0 record delete` (except single-label deletes with `--force-no-confirm` internal flag for agents? — **no**, keep it always, agents use `-y`)
- `rc0 record clear`
- `rc0 record import`
- `rc0 record apply`
- `rc0 dnssec unsign` (double-confirm with `--force`)
- `rc0 dnssec keyrollover`
- `rc0 tsig delete`
- `rc0 messages ack-all`

Confirmation prompts show a dry-run-style summary first, then ask `Type the zone name to confirm:` (gh-style) for zone-level destructive ops. For other destructive ops, a simple `y/N`.

---

## 8. Configuration and authentication

### Config file

**Location:**
- macOS/Linux: `$XDG_CONFIG_HOME/rc0/config.toml` (falls back to `~/.config/rc0/config.toml`)
- Windows: `%APPDATA%\rc0\config.toml`

**Format (TOML):**

```toml
# Default profile
[default]
api_url      = "https://my.rcodezero.at"
output       = "table"
timeout      = 30
retries      = 3
# token is NOT stored here by default — see "token storage" below

# Named profiles for multiple accounts/environments
[profiles.prod]
api_url      = "https://my.rcodezero.at"

[profiles.test]
api_url      = "https://my-test.rcodezero.at"
```

### Token storage

**Preferred:** OS keychain via [`keyring`](https://pypi.org/project/keyring/) (macOS Keychain, Windows Credential Manager, Secret Service on Linux). `rc0 auth login` offers keychain storage first.

**Fallback:** `~/.config/rc0/credentials` with file mode `0600`. If the platform lacks a keyring and the permissions can't be set, refuse to write and emit an error.

**Never** read the token from stdout of anything, never print it, redact it in logs. When a user pipes output, redact tokens in verbose HTTP traces even with `-vv`.

### `rc0 auth login`

- Prompts for token (never echoes).
- Calls `GET /api/v2/zones?page_size=1` to validate.
- On success: offers keychain or plaintext storage.
- On failure: exits 4 (auth error) with a clear message.

---

## 9. Output formats

| `-o` value | Behavior |
|---|---|
| `table` (default, interactive only) | Rich-rendered table. Falls back to `plain` if stdout is not a TTY. |
| `json` | Pretty-printed JSON for humans (indent=2). If `--compact`, single-line. Always valid JSON. |
| `yaml` | PyYAML-dumped, block style. |
| `csv` | Flat, quoted. Columns chosen per resource type. |
| `tsv` | Same as csv with tabs; no quoting. |
| `plain` | Bare text, one record per line, space-separated fields. For pipe-friendliness. |

### Agent-friendliness rules (must follow)

1. **Machine output never writes to stderr unless it's an error.** All normal output goes to stdout.
2. **When `-o json` and an error occurs, the error is JSON on stderr** with the schema in §11.
3. **No ANSI codes in non-table formats**, ever. Even on a TTY.
4. **Exit code is authoritative.** A command never exits 0 on failure.
5. **Deterministic ordering.** JSON arrays are ordered by a documented key (usually `domain` or `id`).
6. **`--jq EXPR`** applies to JSON output before printing. If `jq` binary is missing, the tool falls back to the pure-Python [`jq.py`](https://pypi.org/project/jq/) bindings; if those are also absent, it errors with `exit 10` and a helpful message.

---

## 10. Help system (designed for humans *and* agents)

### Layers

1. **Top-level `rc0 --help`:** Short summary, command groups, common examples, link to docs.
2. **Group help `rc0 zone --help`:** Lists subcommands with one-line summaries.
3. **Command help `rc0 zone create --help`:** Full usage, all flags with types and defaults, 2–3 worked examples, a "See also" section, and an "API" section showing the underlying HTTP call.
4. **Topic help `rc0 help <topic>`:** Long-form guides. Minimum set of topics:
   - `authentication` — how to get a token, how `auth login` works, permission levels, ACME tokens
   - `dnssec-workflow` — sign → ack DS → monitor messages → rollover → unsign
   - `rrset-format` — JSON schema for records, CNAME/ALIAS rules, trailing dots, MX format, maximums (1000 per PATCH, 3000 per PUT)
   - `dry-run` — how dry-run works, what it does and does not do
   - `output-formats` — every format with a real example
   - `pagination` — `--all`, `--page`, `--page-size`, when to use which
   - `exit-codes` — full list (§11)
   - `profiles-and-config` — profiles, env vars, precedence
   - `agents` — how to drive rc0 from a script or LLM agent (see below)
5. **Machine help `rc0 introspect`:** Emits a JSON document describing every command, subcommand, flag, type, default, description, and example. This is the contract for agents — they can enumerate the CLI without parsing help text. Schema:
   ```json
   {
     "rc0_version": "1.0.0",
     "commands": [
       {
         "path": ["zone", "create"],
         "summary": "Add a new zone to RcodeZero.",
         "description": "...",
         "arguments": [
           {"name": "domain", "type": "str", "required": true, "description": "..."}
         ],
         "flags": [
           {"name": "--type", "type": "enum", "values": ["master","slave"], "default": "master", "description": "..."}
         ],
         "examples": [
           {"shell": "rc0 zone create example.com --type master", "explanation": "..."}
         ],
         "api": {"method": "POST", "path": "/api/v2/zones"},
         "destructive": false,
         "deprecated": false,
         "exit_codes": {"0": "success", "4": "auth", "5": "invalid-input", "6": "api-error"}
       }
     ]
   }
   ```

### Help text style rules

- **Lead with the verb.** "Create a new zone." not "This command will create..."
- **Always include at least one example** per command.
- **Show the underlying HTTP call** in a consistent `API: POST /api/v2/zones` line. This satisfies agents and power users who know the API.
- **Warn on destructive flags** inline: `--force` help text begins with `⚠ DANGEROUS:`.
- **Mark deprecated** commands with `[DEPRECATED]` at the start of the summary and link to the replacement.

---

## 11. Error handling and exit codes

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Generic error (unclassified; minimise use) |
| 2 | Usage error (bad flags, missing arguments) — Typer default |
| 3 | Config error (no token, bad config file) |
| 4 | Authentication error (401) |
| 5 | Authorization / permission error (403) |
| 6 | Not found (404) |
| 7 | Validation error (400 with body) |
| 8 | Conflict / already exists (409 or domain-specific) |
| 9 | Rate limited (429) |
| 10 | Network / timeout / DNS failure |
| 11 | Server error (5xx after retries) |
| 12 | Confirmation declined by user |
| 13 | Dry-run completed (success; distinct from 0 so CI can detect dry-runs) — *optional: prefer 0 for compatibility with `gh`/`az`; decide in §18.1* |
| 130 | Interrupted (SIGINT) |

### Error output shape (for `-o json`)

```json
{
  "error": {
    "code": "ZONE_ALREADY_EXISTS",
    "message": "Zone example.com is already configured on the RcodeZero network.",
    "http_status": 409,
    "request": {
      "method": "POST",
      "url": "https://my.rcodezero.at/api/v2/zones",
      "id": "b1a7e9d2-..."
    },
    "hint": "Use `rc0 zone show example.com` to inspect, or add a transfer code if you need to move it between accounts.",
    "docs": "rc0 help zone-transfer"
  }
}
```

Human mode: render the above as a red-bordered panel. Include the `hint` prominently.

### Retry policy

- Retry only **idempotent** GET calls on 429, 502, 503, 504, and network timeouts.
- Exponential backoff with jitter: base 500ms, factor 2, cap 8s.
- Respect `Retry-After` header if present.
- Never retry mutations (POST/PATCH/PUT/DELETE) automatically.

---

## 12. Data formats for RRsets

RRset commands must accept input in three forms; choose whichever the user provides.

### 1. Flag-based (quick set/append/delete)

```bash
# Upsert (default) — works whether the RRset exists or not.
rc0 record set example.com \
  --name www --type A --ttl 3600 \
  --content 10.0.0.1 --content 10.0.0.2

# Strict create-only:
rc0 record set example.com --name www --type A --content 10.0.0.1 --require-absent

# Strict replace-only:
rc0 record set example.com --name www --type A --content 10.0.0.9 --require-exists

# Non-destructive grow (fetch existing → dedupe → PATCH merged set):
rc0 record append example.com --name @ --type MX --content '20 backup-mail.example.com.'
```

- `--name` may be `@` (apex), a leaf label (`www`), or absolute (`www.example.com.`). Relative names are auto-qualified.
- Multiple `--content` aggregate into one RRset (per API rule: a full RRset must be supplied together).
- `record set` maps to `changetype=update` by default; `--require-absent` flips to `changetype=add`.
- `record append` issues a GET first so the merged record list survives the PATCH.

### 2. JSON / YAML file (`--from-file`)

```bash
rc0 record apply example.com --from-file changes.yaml
```

File format mirrors the API request body:

```yaml
- name: www.example.com.
  type: A
  ttl: 3600
  changetype: add
  records:
    - content: 10.0.0.1
- name: www.example.com.
  type: AAAA
  ttl: 3600
  changetype: delete
```

### 3. BIND zone file (`--zone-file`) for `record import` and `record export`

- `export` can emit BIND-format with `-o bind` (non-standard output type, but recognised).
- `import --zone-file ./example.com.zone` parses and submits. Use [`dnspython`](https://pypi.org/project/dnspython/) for parsing — do not roll your own.
- `export` chunks long TXT/SPF content into RFC 1035 §3.3.14 ≤255-byte segments before serialising; this is required to round-trip 2048-bit DKIM keys.

### Validation (client-side, before hitting API)

Before submitting any rrset:
- Enforce trailing dot on `name` (auto-fix, warn in verbose).
- Enforce RRset size limits: **1000 per PATCH, 3000 per PUT.**
- Reject CNAME + other type at the same label.
- Reject MX content without priority.
- Enforce TTL ≥ 60 (RcodeZero minimum; confirm in docs).
- Validate IP addresses for A/AAAA.

---

## 13. Project layout

```
rc0-cli/
├── pyproject.toml
├── README.md
├── LICENSE                          # MIT recommended
├── CHANGELOG.md                     # Keep-a-Changelog format
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                   # lint + type + test on every PR
│   │   ├── release.yml              # tag-triggered: build binaries, publish PyPI, update Homebrew
│   │   └── nightly.yml              # optional: rebuild main against latest deps
│   ├── dependabot.yml
│   └── ISSUE_TEMPLATE/
├── src/rc0/
│   ├── __init__.py                  # __version__
│   ├── __main__.py                  # python -m rc0
│   ├── app.py                       # Typer app root, global flags
│   ├── config.py                    # pydantic-settings
│   ├── auth.py                      # token storage (keyring + fallback)
│   ├── client/                      # HTTP layer
│   │   ├── __init__.py
│   │   ├── http.py                  # httpx.Client wrapper, retries, logging
│   │   ├── errors.py                # exception hierarchy mapped to exit codes
│   │   ├── pagination.py            # auto-paginating iterator
│   │   └── dry_run.py               # request capture + rendering
│   ├── models/                      # Pydantic models for every API request/response
│   │   ├── zone.py
│   │   ├── rrset.py
│   │   ├── tsig.py
│   │   ├── stats.py
│   │   ├── messages.py
│   │   ├── settings.py
│   │   ├── reports.py
│   │   └── acme.py
│   ├── api/                         # Thin functions wrapping each endpoint, returning models
│   │   ├── zones.py
│   │   ├── rrsets.py
│   │   ├── tsig.py
│   │   ├── dnssec.py
│   │   ├── stats.py
│   │   ├── messages.py
│   │   ├── settings.py
│   │   ├── reports.py
│   │   └── acme.py
│   ├── commands/                    # One module per top-level group
│   │   ├── zone.py
│   │   ├── record.py
│   │   ├── dnssec.py
│   │   ├── tsig.py
│   │   ├── stats.py
│   │   ├── report.py
│   │   ├── messages.py
│   │   ├── settings.py
│   │   ├── acme.py
│   │   ├── auth.py
│   │   ├── config.py
│   │   ├── introspect.py
│   │   ├── completion.py
│   │   └── help.py
│   ├── output/                      # Formatters
│   │   ├── table.py
│   │   ├── json_out.py
│   │   ├── yaml_out.py
│   │   ├── csv_tsv.py
│   │   ├── plain.py
│   │   └── bind.py
│   ├── confirm.py                   # Interactive confirmation prompts
│   ├── validation/                  # Client-side validation (rrsets, TTLs, IPs)
│   └── topics/                      # Markdown files for `rc0 help <topic>`
│       ├── authentication.md
│       ├── dnssec-workflow.md
│       ├── rrset-format.md
│       ├── dry-run.md
│       ├── output-formats.md
│       ├── pagination.md
│       ├── exit-codes.md
│       ├── profiles-and-config.md
│       └── agents.md
├── tests/
│   ├── unit/
│   ├── integration/                 # Against a mock server (respx)
│   ├── e2e/                         # Optional, against test env, gated by env var
│   ├── fixtures/
│   │   └── openapi.json             # Pinned copy of rcode0api-v2.json for contract tests
│   └── snapshots/                   # CLI output snapshots
├── docs/
│   ├── index.md
│   ├── quickstart.md
│   ├── recipes/                     # "How do I..." recipes
│   └── api-coverage.md              # Auto-generated matrix from introspect
├── homebrew/
│   └── rc0.rb.template              # Formula template; CI fills in URL + sha256
└── scripts/
    ├── build-binary.sh              # PyInstaller wrapper
    ├── update-openapi.sh            # Refreshes the pinned OpenAPI spec
    └── release.sh
```

---

## 14. Implementation phases

Ship in this order. Each phase ends in a tagged release; do not merge to `main` without tests.

### Phase 0 — Bootstrap (0.1.0)

- Project skeleton, `pyproject.toml`, `uv` lockfile, ruff + mypy + pytest CI.
- `rc0 version`, `rc0 --help`, `rc0 config show`, `rc0 auth login`/`logout`/`status`.
- HTTP client with bearer auth, retries, timeouts, logging.
- Output formatters (table, json, yaml, csv, plain).
- Global flags wired up.
- Error hierarchy with exit-code mapping.

### Phase 1 — Read-only (0.2.0)

- `rc0 zone list`, `rc0 zone show`, `rc0 zone status`.
- `rc0 record list`, `rc0 record export`.
- `rc0 tsig list`, `rc0 tsig show`.
- `rc0 settings show`.
- `rc0 messages list`, `rc0 messages poll`.
- `rc0 stats` (all non-deprecated).
- `rc0 report` (all).
- `rc0 introspect`.
- Pagination: `--all`, `--page`, `--page-size`.

### Phase 2 — Mutations with dry-run (0.3.0)

- `rc0 zone create`, `rc0 zone update`, `rc0 zone enable/disable`, `rc0 zone retrieve`, `rc0 zone test`.
- `rc0 zone xfr-in` and `xfr-out` set/unset.
- `rc0 tsig add/update/delete`.
- `rc0 settings` set/unset for secondaries and TSIG.
- `rc0 messages ack`, `rc0 messages ack-all`.
- Full dry-run support. Confirmation prompts.

### Phase 3 — RRsets, the hard part (0.4.0)

- `rc0 record set/append/delete/apply/import/clear`.
- All three input formats: flags, JSON/YAML file, BIND zone file.
- Client-side validation.
- `rc0 record export` in BIND format.
- Snapshot tests for every rrset operation.

### Phase 4 — DNSSEC (0.5.0)

- `rc0 dnssec sign/unsign/keyrollover/ack-ds`.
- `rc0 dnssec simulate` (test env gate).
- Add `rc0 help dnssec-workflow` topic.

### Phase 5 — ACME (0.6.0)

- `rc0 acme zone-exists/list-challenges/add-challenge/remove-challenge`.
- Document the separate ACME token permission requirement.

### Phase 6 — Packaging & distribution (0.9.0)

- PyInstaller binaries for macOS (arm64, x86_64), Linux (x86_64, arm64), Windows (x86_64).
- GitHub Actions release workflow: tag push → build matrix → PyPI publish → GitHub Release with binaries → Homebrew formula update.
- Homebrew tap (see §16).
- Shell completions installed by the binary.

### Phase 7 — v1.0.0

- Agents topic (`rc0 help agents`) polished.
- Docs site (mkdocs-material).
- Full API coverage confirmed by contract test against pinned `rcode0api-v2.json`.
- Performance pass (cold-start binary <200ms).

---

## 15. Testing strategy

- **Unit tests** (pytest) — pure functions, validators, formatters.
- **Integration tests** — every command invoked via CliRunner; HTTP mocked with `respx`. Assert on: request URL, method, headers, body, and on formatted output (snapshots).
- **Contract tests** — at test time, load the pinned `tests/fixtures/openapi.json`, iterate over every path/method, and assert the client has an implementation for it. Fail if any new endpoint appears in the spec without a CLI command.
- **E2E tests** (optional, gated) — run against the RcodeZero test environment when `RC0_E2E=1` and `RC0_E2E_TOKEN` are set. Not run on every PR; nightly only.
- **Output snapshots** — `pytest-snapshot` stores expected CLI output per format. Updates require explicit `--snapshot-update`.
- **Dry-run parity test** — for every mutation command, run it twice: once with `--dry-run`, once against a mock; assert the captured request is byte-identical.
- **Coverage threshold** — 90% line, 85% branch. Gate in CI.

---

## 16. Release, distribution, and Homebrew

### PyPI

- `uv build` produces wheel + sdist.
- `uv publish` with trusted publishers (OIDC from GitHub Actions) — no API tokens stored.

### Binaries via GitHub Releases

Release workflow (`.github/workflows/release.yml`) triggers on tags `v*.*.*`:

1. **Test matrix** (same as CI).
2. **Build matrix:**
   - `macos-14` → arm64 binary
   - `macos-13` → x86_64 binary
   - `ubuntu-24.04` → x86_64 binary (built in a manylinux container for broad glibc compat)
   - `ubuntu-24.04-arm` → arm64 binary
   - `windows-2025` → x86_64 .exe
3. Each matrix runs PyInstaller with `--onefile --name rc0`, UPX disabled (antivirus false-positive trap), resulting binary name: `rc0-{version}-{os}-{arch}[.exe]`.
4. Strip symbols (Linux/macOS).
5. Generate sha256 checksums per file.
6. **Publish:**
   - Upload all binaries + `SHA256SUMS` to the GitHub Release.
   - `uv publish` to PyPI.
   - Trigger `update-homebrew` job.

### Homebrew

**Tap:** a separate repo `homebrew-rc0` owned by the same user/org.

**Formula (`rc0.rb`):** bottle-style, pulls the macOS binary from the GitHub Release:

```ruby
class Rc0 < Formula
  desc "Command line for RcodeZero DNS"
  homepage "https://github.com/OWNER/rc0-cli"
  version "1.0.0"
  license "MIT"

  on_macos do
    on_arm do
      url "https://github.com/OWNER/rc0-cli/releases/download/v#{version}/rc0-#{version}-macos-arm64"
      sha256 "..."
    end
    on_intel do
      url "https://github.com/OWNER/rc0-cli/releases/download/v#{version}/rc0-#{version}-macos-x86_64"
      sha256 "..."
    end
  end

  on_linux do
    on_arm do
      url "https://github.com/OWNER/rc0-cli/releases/download/v#{version}/rc0-#{version}-linux-arm64"
      sha256 "..."
    end
    on_intel do
      url "https://github.com/OWNER/rc0-cli/releases/download/v#{version}/rc0-#{version}-linux-x86_64"
      sha256 "..."
    end
  end

  def install
    bin.install Dir["rc0-*"].first => "rc0"
    generate_completions_from_executable(bin/"rc0", "completion")
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/rc0 version")
  end
end
```

The release workflow must rewrite URLs + sha256 values in this template and open a PR (or direct push on `main`) to the tap repo using a deploy token.

### Install matrix for end users

- `brew install OWNER/rc0/rc0` (once tap added) — macOS + Linux
- `pip install rc0-cli` or `uv tool install rc0-cli` — everywhere Python runs
- Download binary from GitHub Releases — Windows and air-gapped Linux

---

## 17. Security and hygiene

- **Never log tokens.** Redact `Authorization` headers in every log line and every dry-run output.
- **Secure token storage** — prefer OS keyring; refuse to persist to world-readable files.
- **TLS verification on by default.** `--insecure` flag exists for local test environments but prints a red warning every invocation.
- **Pin minimum dependencies** in `pyproject.toml` with a lock via `uv`.
- **Dependabot** enabled on pip + GitHub Actions.
- **CodeQL / Ruff security rules** enabled.
- **SBOM generation** on release (optional, nice-to-have).
- **Release artifacts signed** with Sigstore/cosign (optional v1.1).

---

## 18. Open decisions — resolve before Phase 0

### 18.1 Dry-run exit code

Pick one and document it in `rc0 help exit-codes`:
- **Option A (recommended):** dry-run exits `0` on success; distinguishable only by the `"dry_run": true` field in JSON output. Matches `gh`, `terraform plan`, and most peer tools.
- **Option B:** dry-run exits `13` on success to let CI treat it distinctly.

**Recommendation: Option A.**

### 18.2 Config file format

TOML is specified above. If a later decision prefers YAML (to match the API request bodies users are already writing), change once and update docs — don't mix.

### 18.3 ACME token detection

Should `rc0 acme *` commands require a separate profile (with the ACME-permissioned token) or should the same profile be reusable? **Recommendation:** reuse profiles; add a `--profile acme` convention in docs; let the API's 403 do the real enforcement and make the error message crystal-clear about the permission scope.

### 18.4 Record-delete confirmation threshold

Single-record delete (`rc0 record delete www.example.com --type A`) — prompt always, or only when the RRset has multiple records and the user is deleting all? **Recommendation:** always prompt; `-y` for scripts. Consistency wins.

### 18.5 Endpoint spec drift

The CLI pins `openapi.json` at build time for contract tests. A nightly job should fetch the live spec and open an issue when it diverges from the pinned copy. Add this as a Phase-7 deliverable, not a Phase-0 blocker.

---

## 19. Acceptance criteria for v1.0.0

A release is v1.0.0-ready when **every** box below is ticked.

- [ ] All non-deprecated endpoints in `rcode0api-v2.json` (v2.9) are exposed as CLI commands.
- [ ] All deprecated endpoints are exposed, hidden from default help, and emit a `[DEPRECATED]` stderr warning when invoked.
- [ ] Every mutation command supports `--dry-run` and produces a parseable intended-request record.
- [ ] Every destructive command (zone delete, record clear, record import, dnssec unsign, tsig delete, messages ack-all) prompts for confirmation unless `-y` is passed.
- [ ] `rc0 --help`, `rc0 <group> --help`, `rc0 <group> <cmd> --help` all render with examples and the underlying API call reference.
- [ ] `rc0 introspect` emits a stable, documented JSON schema of every command.
- [ ] `rc0 help <topic>` works for the 9 topics listed in §10.
- [ ] `-o json` output is valid JSON for every command; errors on stderr are JSON when `-o json`.
- [ ] `-o yaml`, `-o csv`, `-o tsv`, `-o plain` work for every `list`/`show` command.
- [ ] `--jq` works when jq or `jq.py` is available.
- [ ] Exit codes match §11 for every command; `rc0 help exit-codes` lists them.
- [ ] Token storage uses OS keyring when available; `0600` file fallback otherwise.
- [ ] Tokens are never logged, never printed, redacted in dry-run and in verbose HTTP traces.
- [ ] Test coverage ≥ 90% line, ≥ 85% branch.
- [ ] Contract test passes against the pinned `openapi.json`.
- [ ] Cold-start on a 2024-era laptop: `rc0 version` completes in <200ms; `rc0 zone list` round-trip <1s excluding network.
- [ ] Binaries built for macOS arm64, macOS x86_64, Linux x86_64, Linux arm64, Windows x86_64 and attached to each GitHub Release.
- [ ] `pip install rc0-cli` works on Python 3.14+ on all three OSes.
- [ ] `brew install OWNER/rc0/rc0` works on macOS (arm64 and x86_64) and Linuxbrew.
- [ ] Shell completions for bash, zsh, fish, PowerShell are produced by `rc0 completion <shell>` and installed by the Homebrew formula.
- [ ] README has a 60-second quickstart.
- [ ] `docs/api-coverage.md` is auto-generated from introspect and shows a green checkmark per endpoint.
- [ ] CHANGELOG follows Keep-a-Changelog; every PR touches it.

---

## 20. Worked examples (what "done" looks like)

### Add a zone and a record, safely

```bash
$ rc0 auth login
? API token: *************
✓ Authenticated. Token stored in macOS Keychain.

$ rc0 zone create example.com --type master --dry-run -o json
{
  "dry_run": true,
  "request": {
    "method": "POST",
    "url": "https://my.rcodezero.at/api/v2/zones",
    "headers": {"Authorization": "Bearer ***REDACTED***", "Content-Type": "application/json"},
    "body": {"domain": "example.com", "type": "master"}
  },
  "summary": "Would create master zone example.com."
}

$ rc0 zone create example.com --type master
✓ Zone example.com successfully added
  NSSet: sec1.rcode0.net., sec2.rcode0.net.
  Outbound XFR: 83.136.34.10, 2a02:850:9::8 (port 53)

$ rc0 record set example.com --name www --type A --ttl 3600 --content 10.0.0.1
✓ RRset set: www.example.com. A 3600 → 10.0.0.1
```

### Agent-driven zone audit

```bash
$ rc0 -o json zone list --all | jq '.[] | select(.dnssec == "no") | .domain'
"legacy1.example.com"
"legacy2.example.com"
```

### DNSSEC workflow

```bash
$ rc0 dnssec sign example.com -o json
{
  "status": "ok",
  "message": "Zone example.com signed successfully",
  "dnssec_ds": "example.com. IN DS 16747 8 2 A6F8...",
  "dnssec_dnskey": "example.com. IN DNSKEY 257 3 8 AwEAAcAJ..."
}

# ...submit DS to parent zone, wait, then:

$ rc0 dnssec ack-ds example.com
✓ Acknowledged DS update for example.com

$ rc0 messages list --filter-domain example.com -o table
```

### Bulk changes from file

```bash
$ cat changes.yaml
- {name: api.example.com., type: A,    ttl: 60, changetype: add,    records: [{content: 10.0.0.5}]}
- {name: old.example.com., type: A,    changetype: delete}

$ rc0 record apply example.com --from-file changes.yaml --dry-run
Would apply 2 changes to example.com:
  + api.example.com. A 60 → 10.0.0.5
  - old.example.com. A (delete all records)

$ rc0 record apply example.com --from-file changes.yaml
? Type "example.com" to confirm: example.com
✓ RRsets updated (2 changes)
```

---

## 21. Deliverables checklist (for the implementing agent)

Hand these back to the owner at the end of each phase:

1. The code, on a feature branch, with passing CI.
2. Updated `CHANGELOG.md`.
3. Updated `README.md` quickstart if commands changed.
4. New topic files in `src/rc0/topics/` if UX changed.
5. A git tag matching the phase version, annotated with phase summary.
6. A GitHub Release (from Phase 6 onward) with binaries, checksums, and release notes generated from the changelog.
7. A short demo GIF or asciinema recording for the README on Phase 7.

---

## 22. References

- OpenAPI spec (live): https://my.rcodezero.at/openapi/rcode0api-v2.json
- OpenAPI spec (human): https://my.rcodezero.at/openapi/
- RcodeZero workflow docs: https://www.rcodezero.at/en/support/documentation/workflow
- Existing Go client (for API-shape sanity-check): https://github.com/nic-at/rc0go
- Existing certbot plugin (for ACME permission reference): https://github.com/nic-at/certbot-dns-rcode0
- Typer docs: https://typer.tiangolo.com/
- httpx docs: https://www.python-httpx.org/
- PyInstaller docs: https://pyinstaller.org/
- Homebrew formula cookbook: https://docs.brew.sh/Formula-Cookbook

---

*End of mission plan. Ship it.*

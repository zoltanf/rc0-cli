# Changelog

All notable changes to `rc0` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- `record export -f bind` no longer crashes with `SyntaxError: string too long`
  on TXT/SPF records whose content exceeds 255 bytes (e.g. 2048-bit DKIM
  public keys). The renderer now splits long content into RFC 1035 §3.3.14
  ≤255-byte character-strings before constructing the rdata, so multi-string
  TXT round-trips cleanly. A single broken record is now reported on stderr
  and skipped rather than aborting the whole export.
- `record list --name @` and `record list --name <short-label>` now resolve
  to the zone apex / FQDN before hitting the API. Previously the literal
  string was sent and the API silently returned zero rows, masking apex TXT
  and MX records during audits.

### Changed
- `record add` and `record update` help text now spells out that both
  commands replace the full RRset atomically and clarifies the
  pre-existence rule that distinguishes them (`add` rejects when the RRset
  already exists; `update` rejects when it doesn't). The shared `--content`
  help also notes that values together replace the RRset, so existing
  records must be repeated to preserve them.

## [1.1.0] — 2026-04-24

### Changed
- List commands (`zone list`, `record list`, `tsig list`, `messages list`,
  `report problematic-zones`, `acme list-challenges`) now fetch all pages by
  default. Previously they silently truncated at 50 rows (100 for ACME) with
  no indication that more results existed, causing an operational incident
  where records were declared absent because they had been paginated off the
  first page. `--all` remains accepted for script compatibility. `--page N`
  still selects a single page and now prints a stderr warning when more rows
  exist; pass `-q` / `--quiet` to suppress it.

### Fixed
- `tests/unit/test_cli_skill.py::test_install_requires_scope_flag` failed on
  CI because the runner's `FORCE_COLOR=1` environment caused Rich to render
  the `BadParameter` error panel with ANSI escape sequences that split flag
  names (`--project`, `--global`) across styling, breaking the substring
  assertion. The `cli` fixture now pins `COLUMNS`, `NO_COLOR`, and `TERM` so
  the panel always renders as plain text at a wide, predictable width.
- `tests/unit/test_cli_skill.py` skill-install tests failed on Windows CI
  because `Path.home()` on Windows consults `USERPROFILE` before `HOME` —
  the `scoped_fs` fixture only patched `HOME`, so `--global` escaped the
  sandbox and wrote to (or collided with) the runner's real home directory.
  The fixture now patches `USERPROFILE` as well.

## [1.0.8] — 2026-04-24

### Added
- `rc0 skill install` and `rc0 skill uninstall` manage the rc0 Claude Code
  skill. Exactly one of `--project` (installs to `./.claude/skills/rc0/SKILL.md`)
  or `--global` / `-g` (installs to `~/.claude/skills/rc0/SKILL.md`) is
  required. The skill body is bundled as a package resource so it travels
  with both the wheel and the PyInstaller binary. `--dry-run` previews the
  target path without touching disk; a global `-y` skips overwrite and
  removal prompts.

## [1.0.7] — 2026-04-23

### Added
- `rc0 stats queries` and `rc0 stats topzones` now accept `--days N` (1-180),
  forwarded to the API's `days` query parameter. Without the flag the API
  default of 30 days still applies.
- `rc0 stats zone queries` accepts `--days N` as a client-side slice of the
  most recent N days, since the upstream endpoint has no `days` parameter and
  always returns the full 180-day history.
- `rc0 report nxdomains --zone <apex>` filters the report to a single zone
  client-side (trailing dots are ignored). The underlying API has no zone
  parameter for this endpoint, so the filter runs after fetching the full
  account-wide response.

### Changed
- Help text for `rc0 zone list`, `rc0 stats queries`, `rc0 stats zone queries`,
  `rc0 stats topzones`, and `rc0 report nxdomains` now names the output
  columns and their meaning. Previously only the table output carried
  headers; when piped (plain/TSV fallback) users had to guess which column
  was which. Use `-o tsv` or `-o csv` to get headers in redirected output.

## [1.0.6] — 2026-04-23

### Fixed
- `rc0 help list` now enumerates topics in the shipped Homebrew/GitHub-
  Release binaries. The PyInstaller build in `.github/workflows/release.yml`
  was invoking `pyinstaller` with bare flags that did not bundle
  `src/rc0/topics`; the release workflow now passes `--add-data
  src/rc0/topics:rc0/topics` (with `;` on Windows) and runs a post-build
  smoke test (`rc0 help list | grep authentication`) so a regression fails
  CI before a release can ship.
- Every global flag (`-o`/`--output`, `--profile`, `--token`, `--api-url`,
  `--dry-run`, `-y`/`--yes`, `--no-color`, `-q`/`--quiet`,
  `-v`/`--verbose`, `--log-file`, `--timeout`, `--retries`, `--config`,
  `--version`) now parses regardless of position relative to the
  subcommand. `rc0 zone list -o json --all` and `rc0 -o json zone list
  --all` are both valid. Implemented via a small argv pre-parser
  (`rc0.app._hoist_global_flags`) invoked from `main()` before Typer
  dispatch. Tokens after a literal `--` sentinel are passed through
  untouched so user-supplied record values that happen to look like flags
  can still be escaped.

## [1.0.5] — 2026-04-23

### Fixed
- `rc0 report accounting`, `rc0 report queryrates`, and `rc0 report nxdomains`
  returned `[]` for every query even when the account had data. Root cause:
  the API's `type` query parameter defaults to `csv`, so the server was
  returning CSV bodies; `response.json()` then raised `JSONDecodeError` and a
  silent `except` in the client wrapper converted the error into an empty
  list. The wrappers now always send `type=json`, and the swallow is removed
  so real parse errors surface instead of masquerading as empty data.
- `rc0 report nxdomains --day today|yesterday` now passes the keyword through
  to the API literally. The nxdomains endpoint accepts only `'today'` or
  `'yesterday'` (not `YYYY-MM-DD`) — the previous client-side resolution to
  an ISO date was rejected by the server with "The selected day is invalid."
- `rc0 report nxdomains --day YYYY-MM-DD` is now rejected client-side (exit
  2) with a clear message, since the endpoint does not support explicit
  dates. `rc0 report queryrates --day YYYY-MM-DD` continues to work as
  before (that endpoint does accept ISO dates).

### Added
- `scripts/smoke-live.sh` is now an end-to-end live-API integration tour: it
  walks every read-only command (across every output format), performs a
  full create/add/read/update/apply/replace-all/DNSSEC/clear/delete
  round-trip on a throwaway test zone (default `rc0-cli-test.com`), refuses
  to run if that zone already exists, and always cleans up via an EXIT
  trap. Gated by `SKIP_MUTATIONS=1` and `SKIP_DNSSEC=1` env vars.

## [1.0.4] — 2026-04-23

### Fixed
- `rc0 help list` no longer crashes with `ModuleNotFoundError: No module named
  'rc0.topics'` in the PyInstaller binary. The spec now bundles the `topics/`
  directory (`datas`) and declares `rc0.topics` as a hidden import. The `help`
  command also catches `ModuleNotFoundError` at runtime and emits a clean error
  instead of crashing.
- `rc0 report accounting` no longer crashes with `JSONDecodeError` when the API
  returns an empty body (HTTP 2xx, no content). It now returns an empty list.
- `rc0 report nxdomains --day today` (and `--day yesterday`) no longer crashes
  with `JSONDecodeError`. The keywords `today` and `yesterday` are now resolved
  client-side to ISO-format dates (`YYYY-MM-DD`) before the API call is made.
  The same resolution applies to `rc0 report queryrates --day today/yesterday`.
- `rc0 report queryrates` with no `--day` or `--month` now prints a clear
  `BadParameter` message and exits 2 instead of sending an empty request and
  surfacing an opaque API error.

### Changed
- All ~40 help-text examples that showed `rc0 SUBCMD ... -o json` (wrong
  order) have been corrected to `rc0 -o json SUBCMD ...`. The `output-formats`
  topic now documents that `-o`/`--output` is a global flag and must precede
  the subcommand.

## [1.0.3] — 2026-04-23

### Changed
- Extracted `_client`, `_render_mutation`, and `_validate_pagination` into a
  shared `src/rc0/commands/_helpers.py` — eliminates copy-paste across all 9
  command modules.
- Extracted shared `stringify()` formatter into `src/rc0/output/_format.py`;
  `csv_tsv` and `table` modules now import it instead of maintaining local copies.
- Moved `import json` and `from pydantic import ValidationError` to module
  level in `record.py` (were lazily imported inside a function with `_`-aliases).
- Replaced TOCTOU `path.exists()` pre-check in `rrsets/parse.py` with a
  dedicated `FileNotFoundError` branch inside the existing `try/except`.

## [1.0.2] — Startup performance

### Fixed
- `rc0 --help` now responds in ~0.4 s instead of ~12 s when installed via
  Homebrew. The PyInstaller binary is now built with `--onedir` instead of
  `--onefile`; the single-file mode extracted ~80 MB of Python libraries into
  a temp directory on every invocation and macOS XProtect scanned each
  freshly-extracted file.
- Output formatters (`rich`, `pyyaml`, csv) are now imported lazily — only
  loaded when a command actually renders output — reducing Python import time.
- `httpx` (HTTP client) is no longer imported at startup; it is deferred until
  a command makes an API call.

### Changed
- Homebrew formula updated: installs the `rc0/` directory tree to `libexec`
  and symlinks the launcher into `bin` (required by the `--onedir` layout).
- Version strings in `pyproject.toml` and `src/rc0/__init__.py` are now kept
  in sync with the release tag (were frozen at `1.0.0`).

## [1.0.1] — Post-release fixes

### Added
- `.github/workflows/nightly.yml` — nightly spec-drift job: fetches the live
  OpenAPI spec, diffs against `tests/fixtures/openapi.json`, and opens a
  `spec-drift` GitHub Issue when divergence is detected (§18.5).
- 40 new unit tests covering `output/table.py`, `output/plain.py`, and
  `output/csv_tsv.py` (all three now at 100% line coverage).

### Changed
- Coverage gate raised from 87% → 88% (actual: 89.2% macOS / ~88% Windows).

### Fixed
- Release workflow (`release.yml`) now passes on Windows: the two skipped
  auth tests on Windows reduced coverage to 86%, below the old 87% gate.
- macOS binary is no longer killed on launch: `strip` is now skipped on macOS
  so PyInstaller's embedded archive and its ad-hoc signature remain intact.

## [1.0.0] — v1.0.0 Polish

### Added
- `rc0 help agents` topic — how to drive rc0 from scripts and LLM agents:
  machine-readable output, exit codes, dry-run, `rc0 introspect`, pagination,
  CI token management, and the recommended agent pattern.
- `docs/api-coverage.md` auto-generated from `scripts/gen_api_coverage.py`;
  63/63 endpoints in the pinned OpenAPI spec mapped with ✅/⚠️ status.
- `scripts/gen_api_coverage.py` — generates `docs/api-coverage.md` from the
  pinned spec; run with `uv run python scripts/gen_api_coverage.py`.

### Changed
- Coverage gate raised from 86% → 87% (actual: 87.21%).
- `pyproject.toml` classifier updated from Alpha → Production/Stable.
- All key command help texts now include worked examples in `--help` output:
  `zone` (list/show/create/update/delete), `record` (list/add/update/delete),
  `dnssec` (sign/unsign/ack-ds), `acme` (all four commands), `auth` (login/
  logout/status), `tsig` (list/add/delete), `messages` (list/ack-all).

## [0.9.0] — Packaging & Distribution

### Added
- GitHub Actions release workflow (`.github/workflows/release.yml`): tag push →
  test matrix on all five platforms → PyInstaller binary build matrix →
  PyPI publish via OIDC trusted publisher → GitHub Release with all binaries
  and `SHA256SUMS`.
- PyInstaller dependency group in `pyproject.toml` (`uv sync --group pyinstaller`).
- Homebrew formula template (`packaging/homebrew/rc0.rb`); the release workflow
  populates version + sha256 and pushes it to the `homebrew-rc0` tap repo.
- Dependabot configuration for pip and GitHub Actions dependencies (weekly).
- Expanded CI test matrix (`ci.yml`) to all five spec platforms: `ubuntu-24.04`,
  `ubuntu-24.04-arm`, `macos-14`, `macos-13`, `windows-2025`.
- README quickstart with install instructions, authentication, and example commands.

### Fixed
- `actions/checkout@v6` (non-existent) corrected to `actions/checkout@v4` in CI.

## [0.6.0] — ACME

### Added
- `rc0 acme zone-exists <zone>` — GET `/api/v1/acme/{zone}`; confirms the zone is configured for ACME; exits 6 if not found.
- `rc0 acme list-challenges <zone>` — GET `/api/v1/acme/zones/{zone}/rrsets`; paginated list of `_acme-challenge.` TXT records; supports `--page`, `--page-size`, `--all`.
- `rc0 acme add-challenge <zone> --value TOKEN [--ttl 60]` — PATCH to add a DNS-01 challenge TXT record; supports `--dry-run`.
- `rc0 acme remove-challenge <zone>` — PATCH with `changetype: delete` to remove all `_acme-challenge.` TXT records; y/N confirmation (`-y` to skip); supports `--dry-run`.
- 403 responses on all `acme` commands carry an explicit hint about the ACME token permission (§18.3).
- Topic help: `acme-workflow` (`rc0 help acme-workflow`) — DNS-01 overview, token setup, certbot hook examples.
- Dry-run parity extended: `test_dry_run_parity.py` covers both ACME mutations.

## [0.5.0] — DNSSEC

### Added
- `rc0 dnssec sign <zone>` — POST `/zones/{zone}/sign`; optional `--ignore-safety-period` and `--enable-cds-cdnskey` flags; no confirmation.
- `rc0 dnssec unsign <zone>` — POST `/zones/{zone}/unsign`; requires `--force` flag + y/N confirmation to prevent accidental key removal.
- `rc0 dnssec keyrollover <zone>` — POST `/zones/{zone}/keyrollover`; y/N confirmation (`-y` to skip).
- `rc0 dnssec ack-ds <zone>` — POST `/zones/{zone}/dsupdate`; no confirmation; clears DSUPDATE messages from the queue.
- `rc0 dnssec simulate dsseen <zone>` — POST `/zones/{zone}/simulate/dsseen`; test environments only (blocked against production API).
- `rc0 dnssec simulate dsremoved <zone>` — POST `/zones/{zone}/simulate/dsremoved`; test environments only.
- Topic help: `dnssec-workflow` (`rc0 help dnssec-workflow`) — full lifecycle: sign → ack DS → keyrollover → unsign, plus simulate usage.
- Dry-run parity extended: `test_dry_run_parity.py` now covers all four network-capable DNSSEC mutations.

## [0.4.0] — RRsets

### Added
- `rc0 record add <zone>` — PATCH a single RRset via flags; no confirmation.
- `rc0 record update <zone>` — PATCH changetype `update` via flags; no confirmation.
- `rc0 record delete <zone>` — PATCH changetype `delete` via flags; y/N confirmation (`-y` to skip).
- `rc0 record apply <zone> --from-file FILE` — PATCH from a JSON/YAML changes file (mixed changetypes); typed-zone confirmation.
- `rc0 record replace-all <zone> --from-file FILE | --zone-file BIND` — PUT full zone replacement from JSON/YAML or BIND zone file; typed-zone confirmation.
- `rc0 record clear <zone>` — DELETE all non-apex rrsets; typed-zone confirmation.
- Client-side validation for all RRset mutations (§12): TTL ≥ 60 s, A/AAAA content sanity, MX `priority content` format (priority 0–65535), PATCH ≤ 1000 changes, PUT ≤ 3000 rrsets, CNAME exclusivity. Validation errors exit 7.
- Three input parsers in `rc0.rrsets.parse`: flag-based (`from_flags`), JSON/YAML file (`from_file`), BIND zone-file (`from_zonefile` via dnspython).
- Trailing-dot auto-qualification: names without a trailing dot are silently qualified to FQDN; `--verbose` prints a warning per corrected label.
- Topic help: `rrset-format` (`rc0 help rrset-format`).
- Dry-run parity extended: `test_dry_run_parity.py` now covers all six new rrset mutations (4 parametrised + 2 fixture-based standalone tests).

### Changed
- `[tool.coverage.report] fail_under` raised from 84 → 86 to lock in Phase-3 coverage gain (actual: ~86.9% on macOS/Linux).

## [0.3.0] — Mutations with dry-run

### Added
- `rc0 zone create/update/enable/disable/delete/retrieve/test`.
- `rc0 zone xfr-in show/set/unset` and `rc0 zone xfr-out show/set/unset`.
- `rc0 tsig add/update/delete`.
- `rc0 settings secondaries/tsig-in/tsig-out set/unset`.
- `rc0 messages ack/ack-all`.
- `--dry-run` on every new mutation. Exit code 0; machine output carries
  `"dry_run": true`. The paging executor (`rc0.client.mutations`) shares
  one dispatcher between the dry-run and live code paths.
- Confirmation prompts for destructive operations: `zone delete` requires
  typing the zone name, `tsig delete` and `messages ack-all` accept a
  simple y/N. `-y` / `--yes` skips; `--dry-run` skips.
- Topic help: `dry-run`.
- Pydantic `Rc0WriteModel` base (with `extra="forbid"`) for every request
  body — typos and drift-with-the-spec fail loudly at construction time.

### Changed
- Contract test `PHASE_2_OR_LATER` tolerance set emptied — both
  `/zones/{zone}/inbound` and `/zones/{zone}/outbound` GET paths are now
  implemented as `rc0 zone xfr-in show` / `rc0 zone xfr-out show`.
- `build_dry_run()` now accepts a `params=` kwarg so dry-run URLs carry
  query strings (needed for `rc0 zone test`).
- `[tool.coverage.report] fail_under` raised from 78 → 84 to lock in the
  Phase-2 coverage gain (actual: 85.7% on macOS/Linux, 84.3% on Windows
  where file-fallback credential paths skip by design).

### Added (testing)
- `tests/unit/test_dry_run_parity.py` — every Phase 2 mutation runs twice
  (dry-run + mocked live) and the captured HTTP request must be
  byte-identical (method, URL, body). This is the mission-plan §15 gate.
- Full CLI integration coverage for every new command.
- Unit coverage for `rc0.confirm` (typed + yes/no flows).

## [0.2.0] — Read-only commands

### Added
- `rc0 zone list/show/status` — zone browsing with auto-pagination.
- `rc0 record list/export` — RRset browsing; `record export` supports
  `-f bind` (via `dnspython`), `-f json`, and `-f yaml`.
- `rc0 tsig list/show` and hidden `tsig list-out` (deprecated endpoint).
- `rc0 settings show` — account-level settings.
- `rc0 messages poll/list` — the message queue.
- `rc0 stats queries/topzones/countries` and `rc0 stats zone queries`,
  plus six hidden deprecated stats commands that emit a `[DEPRECATED]`
  warning on stderr when invoked.
- `rc0 report problematic-zones/nxdomains/accounting/queryrates/domainlist`.
- `rc0 introspect` — JSON schema of every command for agent / script use.
- Topic help pages: `pagination`, `profiles-and-config`.

### Changed
- The auto-paginator now handles **both** the Laravel pagination envelope
  (`/api/v2/zones`, `/rrsets`, `/messages/list`, `/reports/problematiczones`)
  and bare-array responses (`/tsig`, `/stats/*`, most reports) — no caller
  changes needed.
- `RC0_SUPPRESS_DEPRECATED` now only silences the warning for truthy
  values (`1`, `true`, `yes`, `on`, case-insensitive). Any other value —
  including `0` and `false` — leaves the warning enabled.
- `[tool.coverage.report] fail_under` raised from 70 → 78 to lock in the
  Phase-1 coverage gain (current: 81%+).

### New dependencies
- `dnspython>=2.7` — BIND zone-file rendering for `rc0 record export -f bind`.

### Added (testing)
- Contract test (`tests/contract/test_openapi_coverage.py`) asserts every
  non-deprecated v2 `GET` in the pinned OpenAPI spec maps to a CLI command
  — mechanical safety net for future spec bumps.

## [0.1.0] — Bootstrap

### Added
- Project skeleton: `pyproject.toml`, src/ layout, CI, ruff + mypy --strict + pytest.
- `rc0 version`, `rc0 --help`, `rc0 config show/get/set/unset/path`.
- `rc0 auth login/logout/status` with OS keyring storage and `0600` file fallback.
- HTTP client wrapper over httpx: bearer auth, idempotent retries with jitter,
  request/response logging with `Authorization` header redaction.
- Output formatters: table, json, yaml, csv, tsv, plain.
- Global flags per mission plan §6.
- Error hierarchy mapped to exit codes per mission plan §11.
- Topic help: `authentication`, `exit-codes`, `output-formats`.

[Unreleased]: https://github.com/zoltanf/rc0-cli/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/zoltanf/rc0-cli/releases/tag/v0.4.0
[0.3.0]: https://github.com/zoltanf/rc0-cli/releases/tag/v0.3.0
[0.2.0]: https://github.com/zoltanf/rc0-cli/releases/tag/v0.2.0
[0.1.0]: https://github.com/zoltanf/rc0-cli/releases/tag/v0.1.0

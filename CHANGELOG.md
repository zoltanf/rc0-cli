# Changelog

All notable changes to `rc0` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

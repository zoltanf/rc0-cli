# Changelog

All notable changes to `rc0` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/zoltanf/rc0-cli/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/zoltanf/rc0-cli/releases/tag/v0.3.0
[0.2.0]: https://github.com/zoltanf/rc0-cli/releases/tag/v0.2.0
[0.1.0]: https://github.com/zoltanf/rc0-cli/releases/tag/v0.1.0

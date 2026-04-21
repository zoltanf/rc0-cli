# Changelog

All notable changes to `rc0` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/zoltanf/rc0-cli/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/zoltanf/rc0-cli/releases/tag/v0.1.0

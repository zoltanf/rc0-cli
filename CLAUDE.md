# rc0 — project context for Claude Code

This directory hosts **`rc0`** (PyPI `rc0-cli`), a production-grade Python
3.14 CLI for the [RcodeZero Anycast DNS API](https://my.rcodezero.at/openapi/)
(v2 + v1 ACME).

## Authoritative docs

- **[docs/rc0-cli-mission-plan.md](docs/rc0-cli-mission-plan.md)** — the
  design doc. 22 sections covering command tree, global flags, dry-run
  contract, config/auth, output formats, exit codes, rrset data formats,
  testing strategy, packaging, and the 7-phase release ladder. Now a
  reference document, not a roadmap — every phase shipped. Still the
  authority on command shape and conventions; **read the relevant
  section before touching any code**.

## Settled tactical decisions

| Decision | Value |
|---|---|
| License | MIT |
| GitHub owner | `zoltanf` (personal; transferable later) |
| Python floor | 3.14.4+ |
| CLI / HTTP / models | Typer ≥0.15 / httpx ≥0.28 / Pydantic v2 |
| Config format | TOML (mission plan §18.2) |
| Dry-run exit code | 0 on success (§18.1 Option A) |
| ACME token | Reuse profiles; rely on API 403 + clear error message (§18.3) |
| Record-delete confirm | Always prompt; `-y` for scripts (§18.4) |
| Binary builder | PyInstaller for now; re-evaluate vs Nuitka in Phase 6 |
| Spec-drift job | Nightly; Phase 7 deliverable (§18.5) |

## Release status

All seven mission-plan phases shipped (v0.1.0 → v1.0.0). The project is
post-v1.0; ongoing work is patch/minor releases driven by user feedback
and small UX polish, not phased delivery. See `CHANGELOG.md` for what
each version added.

## Working conventions

- Feature work goes on a topic branch and merges to `main` via PR.
- No merge without green CI (mission plan §14).
- Every PR updates `CHANGELOG.md` (Keep-a-Changelog format) — add entries
  under the existing `## [Unreleased]` block only.
- **Releases go through `scripts/release.sh <version>`.** Fix/feature PRs
  must NOT bump `pyproject.toml`, `src/rc0/__init__.py`, or add a dated
  `## [X.Y.Z] — YYYY-MM-DD` heading — the script handles all three, plus
  the commit, tag, and push that triggers the release workflow.

## Local verification (run before every commit)

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

Coverage target per mission plan §15: 90% line / 85% branch. Current
`fail_under` gate is 88 (per `pyproject.toml`); actual coverage on
`main` is ~91%.

## Security reminders (mission plan §17)

- Never log tokens. `Authorization` header is redacted by
  `Client.redact_headers` and in every dry-run output.
- Tokens live in the OS keyring (preferred) or `~/.config/rc0/credentials`
  with mode 0600. Refuse plaintext fallback on Windows.
- `--insecure` is available for test environments but must warn loudly.

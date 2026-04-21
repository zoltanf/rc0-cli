# rc0 — project context for Claude Code

This directory hosts **`rc0`** (PyPI `rc0-cli`), a production-grade Python
3.14 CLI for the [RcodeZero Anycast DNS API](https://my.rcodezero.at/openapi/)
(v2 + v1 ACME).

## Authoritative docs

- **[docs/rc0-cli-mission-plan.md](docs/rc0-cli-mission-plan.md)** — the
  design doc. 22 sections covering command tree, global flags, dry-run
  contract, config/auth, output formats, exit codes, rrset data formats,
  testing strategy, packaging, and the 7-phase release ladder.
  **Read the relevant section before touching any code** — this CLAUDE.md
  is a pointer, not a substitute.
- **`~/.claude/plans/let-s-make-this-happen-ancient-naur.md`** — the
  meta-plan that carves the mission plan into phases and records tactical
  decisions.

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

## Phase status

| Phase | Tag | Status |
|---|---|---|
| 0 Bootstrap | v0.1.0 | **Done** (2026-04-21). Project skeleton, auth, config, HTTP client, output formatters, topic help. |
| 1 Read-only | v0.2.0 | **Done** (2026-04-21). Every non-deprecated v2 GET reachable as a CLI command; `rc0 introspect`; auto-paginator speaks both envelope and bare-array shapes; contract test gates the release. |
| 2 Mutations with dry-run | v0.3.0 | Pending — next up. |
| 3 RRsets | v0.4.0 | Pending. |
| 4 DNSSEC | v0.5.0 | Pending. |
| 5 ACME | v0.6.0 | Pending. |
| 6 Packaging & distribution | v0.9.0 | Pending. |
| 7 v1.0.0 polish | v1.0.0 | Pending. |

## Working conventions

- One feature branch per phase (`phase-N-<slug>`). Merge to `main` via PR.
  Annotated tag at the end of each phase.
- No merge without green CI (mission plan §14).
- Every PR updates `CHANGELOG.md` (Keep-a-Changelog format).
- Each phase gets its own detailed implementation plan via
  `superpowers:writing-plans` — do **not** treat the meta-plan as the
  execution plan.

## Local verification (run before every commit)

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

Coverage target per mission plan §15: 90% line / 85% branch. Current
`fail_under` gate is 78 (Phase-1 floor; actual coverage ~81%). Tighten
the gate further as each phase lands real code.

## Security reminders (mission plan §17)

- Never log tokens. `Authorization` header is redacted by
  `Client.redact_headers` and in every dry-run output.
- Tokens live in the OS keyring (preferred) or `~/.config/rc0/credentials`
  with mode 0600. Refuse plaintext fallback on Windows.
- `--insecure` is available for test environments but must warn loudly.

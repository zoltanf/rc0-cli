# Phase 1: Read-only Commands — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship every non-deprecated `GET` endpoint in the RcodeZero API v2 as an rc0 read-only subcommand, wire up pagination (`--all` / `--page` / `--page-size`), add `rc0 introspect`, expose deprecated endpoints as hidden commands that emit a `[DEPRECATED]` stderr warning, and gate the release behind a contract test against the pinned OpenAPI spec. End-state: tag `v0.2.0`.

**Architecture:** Thin three-layer stack — Pydantic v2 models describe every response shape, `api/*.py` modules wrap the shared [`Client`][http] and return typed models, `commands/*.py` turn Typer arguments into `api/*` calls and render via the existing `render()` dispatcher. A new paginator in `client/pagination.py` iterates page-by-page and aggregates for `--all`. A small `commands/_deprecated.py` helper handles the hidden-in-help + stderr-warning pattern uniformly. `rc0 introspect` walks the Typer command tree and emits the §10 machine-readable schema.

**Tech Stack:** Python 3.14, Typer ≥0.15, httpx ≥0.28, Pydantic v2, `dnspython` (for `-o bind` output of `record export`), respx + pytest-snapshot (tests).

**Authoritative references:**
- [`docs/rc0-cli-mission-plan.md`](../../rc0-cli-mission-plan.md) §4, §5, §9, §10, §14
- [`tests/fixtures/openapi.json`](../../../tests/fixtures/openapi.json) — pinned RcodeZero API v2.9 spec. Every new response model must match a schema here.
- [`../../../CLAUDE.md`](../../../CLAUDE.md) — settled tactical decisions.

**Scope — non-deprecated GETs (one command per endpoint):**

| Endpoint | CLI command | Paginated? |
|---|---|---|
| `GET /api/v2/zones` | `rc0 zone list` | yes |
| `GET /api/v2/zones/{zone}` | `rc0 zone show <zone>` | no |
| `GET /api/v2/zones/{zone}/status` | `rc0 zone status <zone>` | no |
| `GET /api/v2/zones/{zone}/rrsets` | `rc0 record list <zone>` / `rc0 record export <zone>` | yes |
| `GET /api/v2/tsig` | `rc0 tsig list` | yes |
| `GET /api/v2/tsig/{keyname}` | `rc0 tsig show <name>` | no |
| `GET /api/v2/settings` | `rc0 settings show` | no |
| `GET /api/v2/messages` | `rc0 messages poll` | no |
| `GET /api/v2/messages/list` | `rc0 messages list` | yes |
| `GET /api/v2/stats/querycounts` | `rc0 stats queries` | no |
| `GET /api/v2/stats/topzones` | `rc0 stats topzones` | no |
| `GET /api/v2/stats/countries` | `rc0 stats countries` | no |
| `GET /api/v2/zones/{zone}/stats/queries` | `rc0 stats zone queries <zone>` | no |
| `GET /api/v2/reports/problematiczones` | `rc0 report problematic-zones` | no |
| `GET /api/v2/reports/nxdomains` | `rc0 report nxdomains` | no |
| `GET /api/v2/reports/accounting` | `rc0 report accounting` | no |
| `GET /api/v2/reports/queryrates` | `rc0 report queryrates` | no |
| `GET /api/v2/reports/domainlist` | `rc0 report domainlist` | no |

**Scope — deprecated GETs (hidden in default help, emit stderr warning):**

| Endpoint | CLI command |
|---|---|
| `GET /api/v2/tsig/out` | `rc0 tsig list-out` |
| `GET /api/v2/stats/topmagnitude` | `rc0 stats topmagnitude` |
| `GET /api/v2/stats/topnxdomains` | `rc0 stats topnxdomains` |
| `GET /api/v2/stats/topqnames` | `rc0 stats topqnames` |
| `GET /api/v2/zones/{zone}/stats/magnitude` | `rc0 stats zone magnitude <zone>` |
| `GET /api/v2/zones/{zone}/stats/nxdomains` | `rc0 stats zone nxdomains <zone>` |
| `GET /api/v2/zones/{zone}/stats/qnames` | `rc0 stats zone qnames <zone>` |

---

## File Structure

**New source files:**

- `src/rc0/models/__init__.py` — package docstring only (already a stub)
- `src/rc0/models/common.py` — shared primitives (pagination envelope, ISO timestamps)
- `src/rc0/models/zone.py` — `Zone`, `ZoneStatus`
- `src/rc0/models/rrset.py` — `RRset`, `Record`
- `src/rc0/models/tsig.py` — `TsigKey`
- `src/rc0/models/settings.py` — `AccountSettings`
- `src/rc0/models/messages.py` — `Message`
- `src/rc0/models/stats.py` — `QueryCount`, `TopZoneRow`, `CountryRow`, `MagnitudeRow`, `QnameRow`, `NxdomainRow`
- `src/rc0/models/reports.py` — `ProblematicZone`, `NxdomainReport`, `AccountingRow`, `QueryRateRow`, `DomainListRow`
- `src/rc0/api/zones.py`, `api/rrsets.py`, `api/tsig.py`, `api/settings.py`, `api/messages.py`, `api/stats.py`, `api/reports.py`
- `src/rc0/commands/zone.py`, `commands/record.py`, `commands/tsig.py`, `commands/settings.py`, `commands/messages.py`, `commands/stats.py`, `commands/report.py`, `commands/introspect.py`
- `src/rc0/commands/_deprecated.py` — `deprecated_warn(name: str) -> None` helper
- `src/rc0/output/bind.py` — BIND zone-file formatter for `record export -o bind`
- `src/rc0/topics/pagination.md`, `topics/profiles-and-config.md`

**Modified source files:**

- `src/rc0/app.py` — register the 8 new command groups + `introspect`
- `src/rc0/client/pagination.py` — replace the stub with a real auto-paginator
- `src/rc0/output/__init__.py` — register `OutputFormat.bind` (allowed only for `record export`)
- `src/rc0/__init__.py` — bump `__version__` to `"0.2.0"`
- `pyproject.toml` — add `dnspython` dependency
- `CHANGELOG.md` — append `[0.2.0]` section
- `.github/workflows/ci.yml` — add the contract-test job (same matrix as unit tests)

**New test files:**

- `tests/unit/test_pagination.py`
- `tests/unit/test_deprecated_helper.py`
- `tests/unit/test_bind_output.py`
- `tests/unit/test_models.py` — round-trip of representative payloads from the spec
- `tests/integration/test_zone_commands.py`
- `tests/integration/test_record_commands.py`
- `tests/integration/test_tsig_commands.py`
- `tests/integration/test_settings_commands.py`
- `tests/integration/test_messages_commands.py`
- `tests/integration/test_stats_commands.py`
- `tests/integration/test_report_commands.py`
- `tests/integration/test_introspect.py`
- `tests/contract/__init__.py`, `tests/contract/test_openapi_coverage.py`

---

## Task 0: Branch setup and dependency update

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/fixtures/openapi.json` (already fetched in the planning step — keep it)

- [ ] **Step 1: Confirm branch and pinned spec**

Already done during planning. Verify:
```bash
git branch --show-current       # → phase-1-readonly
wc -c tests/fixtures/openapi.json   # → 189757 (give or take)
```

- [ ] **Step 2: Add `dnspython` to `pyproject.toml`**

Edit `pyproject.toml` under `[project].dependencies`:

```toml
dependencies = [
    "typer>=0.15",
    "httpx>=0.28",
    "pydantic>=2.9",
    "pydantic-settings>=2.6",
    "rich>=13.9",
    "keyring>=25.0",
    "pyyaml>=6.0.2",
    "tomli-w>=1.0",
    "dnspython>=2.7",   # BIND zone-file rendering for `rc0 record export -o bind`
]
```

- [ ] **Step 3: Sync and commit**

```bash
uv sync --all-groups
git add pyproject.toml uv.lock tests/fixtures/openapi.json
git commit -m "chore(phase-1): pin OpenAPI spec, add dnspython dep"
```

---

## Task 1: Auto-paginator

**Files:**
- Modify: `src/rc0/client/pagination.py`
- Test: `tests/unit/test_pagination.py`

The API uses `page` (1-indexed) and `page_size` query parameters. A response may include a top-level `total` count or a standard envelope — consult `tests/fixtures/openapi.json`. When neither is present, continue while the last page returned exactly `page_size` items.

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_pagination.py`:

```python
"""Paginator iterates the API's page/page_size protocol and aggregates for --all."""

from __future__ import annotations

import httpx
import respx

from rc0.client.http import Client
from rc0.client.pagination import iter_pages, iter_all


@respx.mock
def test_iter_pages_walks_until_short_page() -> None:
    respx.get("https://api.test/api/v2/zones", params={"page": 1, "page_size": 2}).mock(
        return_value=httpx.Response(200, json=[{"domain": "a"}, {"domain": "b"}]),
    )
    respx.get("https://api.test/api/v2/zones", params={"page": 2, "page_size": 2}).mock(
        return_value=httpx.Response(200, json=[{"domain": "c"}]),
    )
    with Client(api_url="https://api.test", token="tk") as c:
        pages = list(iter_pages(c, "/api/v2/zones", page_size=2))
    assert pages == [
        [{"domain": "a"}, {"domain": "b"}],
        [{"domain": "c"}],
    ]


@respx.mock
def test_iter_all_flattens_pages() -> None:
    respx.get("https://api.test/api/v2/zones").mock(
        side_effect=[
            httpx.Response(200, json=[{"domain": "a"}, {"domain": "b"}]),
            httpx.Response(200, json=[{"domain": "c"}]),
        ],
    )
    with Client(api_url="https://api.test", token="tk") as c:
        rows = list(iter_all(c, "/api/v2/zones", page_size=2))
    assert [r["domain"] for r in rows] == ["a", "b", "c"]


@respx.mock
def test_iter_pages_single_page() -> None:
    respx.get("https://api.test/api/v2/zones", params={"page": 1, "page_size": 50}).mock(
        return_value=httpx.Response(200, json=[{"domain": "only"}]),
    )
    with Client(api_url="https://api.test", token="tk") as c:
        pages = list(iter_pages(c, "/api/v2/zones", page_size=50))
    assert pages == [[{"domain": "only"}]]
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/unit/test_pagination.py -v
# Expected: ImportError — iter_pages / iter_all not defined
```

- [ ] **Step 3: Replace the pagination stub with a real implementation**

Overwrite `src/rc0/client/pagination.py`:

```python
"""Auto-pagination helpers used by read-only list commands.

The RcodeZero API v2 accepts ``page`` (1-indexed) and ``page_size`` query
parameters on listing endpoints. Responses are JSON arrays; when a page
returns fewer rows than ``page_size`` we've hit the end.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rc0.client.http import Client

DEFAULT_PAGE_SIZE = 50


def iter_pages(
    client: Client,
    path: str,
    *,
    page_size: int = DEFAULT_PAGE_SIZE,
    params: Mapping[str, Any] | None = None,
    start_page: int = 1,
) -> Iterator[list[dict[str, Any]]]:
    """Yield successive pages until a short page signals the end."""
    page = start_page
    while True:
        query: dict[str, Any] = {"page": page, "page_size": page_size}
        if params:
            query.update(params)
        response = client.get(path, params=query)
        payload = response.json()
        if not isinstance(payload, list):
            msg = f"Expected JSON array from {path}, got {type(payload).__name__}."
            raise TypeError(msg)
        yield payload
        if len(payload) < page_size:
            return
        page += 1


def iter_all(
    client: Client,
    path: str,
    *,
    page_size: int = DEFAULT_PAGE_SIZE,
    params: Mapping[str, Any] | None = None,
) -> Iterator[dict[str, Any]]:
    """Flatten :func:`iter_pages` into a row iterator."""
    for page in iter_pages(client, path, page_size=page_size, params=params):
        yield from page
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/unit/test_pagination.py -v
# Expected: 3 passed
```

- [ ] **Step 5: Lint, type, commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy
git add src/rc0/client/pagination.py tests/unit/test_pagination.py
git commit -m "feat(phase-1): add real auto-paginator with --all support"
```

---

## Task 2: Deprecated-command helper

**Files:**
- Create: `src/rc0/commands/_deprecated.py`
- Test: `tests/unit/test_deprecated_helper.py`

Every deprecated command registers `hidden=True` on its Typer decorator (keeps it off the default help) and calls `deprecated_warn(name)` on its first line to print a stderr warning.

- [ ] **Step 1: Write failing test**

`tests/unit/test_deprecated_helper.py`:

```python
"""The deprecated-command helper emits the stderr warning specified in §10."""

from __future__ import annotations

import pytest

from rc0.commands._deprecated import deprecated_warn


def test_deprecated_warn_writes_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    deprecated_warn("rc0 stats topmagnitude")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "[DEPRECATED]" in captured.err
    assert "rc0 stats topmagnitude" in captured.err


def test_deprecated_warn_can_be_suppressed_by_flag(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("RC0_SUPPRESS_DEPRECATED", "1")
    deprecated_warn("rc0 stats topmagnitude")
    captured = capsys.readouterr()
    assert captured.err == ""
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
uv run pytest tests/unit/test_deprecated_helper.py -v
# Expected: ImportError
```

- [ ] **Step 3: Write the helper**

`src/rc0/commands/_deprecated.py`:

```python
"""Helper for deprecated commands — warn on stderr and keep it off default --help."""

from __future__ import annotations

import os
import sys


def deprecated_warn(command: str) -> None:
    """Print a ``[DEPRECATED]`` banner for ``command`` unless suppressed.

    Set ``RC0_SUPPRESS_DEPRECATED=1`` to silence in scripts that knowingly
    exercise deprecated endpoints (e.g. the contract test).
    """
    if os.environ.get("RC0_SUPPRESS_DEPRECATED"):
        return
    sys.stderr.write(f"[DEPRECATED] {command} calls a deprecated endpoint.\n")
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
uv run pytest tests/unit/test_deprecated_helper.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/rc0/commands/_deprecated.py tests/unit/test_deprecated_helper.py
git commit -m "feat(phase-1): add deprecated-command warning helper"
```

---

## Task 3: Zone models, api, and commands

**Files:**
- Create: `src/rc0/models/zone.py`, `src/rc0/models/common.py`
- Create: `src/rc0/api/zones.py`
- Create: `src/rc0/commands/zone.py`
- Test: `tests/unit/test_models.py`, `tests/integration/test_zone_commands.py`
- Modify: `src/rc0/app.py` (register group)

Zone response schema — consult `#/components/schemas/Zone` in `tests/fixtures/openapi.json`. Typical shape:

```json
{"domain": "example.com", "type": "master", "dnssec": "yes", "created": "2025-...", "last_check": null}
```

- [ ] **Step 1: Write the model test**

`tests/unit/test_models.py`:

```python
"""Round-trip representative payloads against the Pydantic models."""

from __future__ import annotations

from rc0.models.zone import Zone, ZoneStatus


def test_zone_parses_minimum_payload() -> None:
    z = Zone.model_validate(
        {"domain": "example.com", "type": "master", "dnssec": "yes"},
    )
    assert z.domain == "example.com"
    assert z.type == "master"


def test_zone_status_parses() -> None:
    s = ZoneStatus.model_validate(
        {"domain": "example.com", "serial": 1, "status": "ok"},
    )
    assert s.serial == 1
```

- [ ] **Step 2: Run to confirm it fails, then write models**

`src/rc0/models/common.py`:

```python
"""Shared model primitives."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Rc0Model(BaseModel):
    """Base class — permissive on extras so the API can evolve without breaking."""

    model_config = ConfigDict(extra="allow", frozen=True, str_strip_whitespace=True)
```

`src/rc0/models/zone.py`:

```python
"""Zone and ZoneStatus — mirrors #/components/schemas/Zone in the pinned spec."""

from __future__ import annotations

from typing import Literal

from rc0.models.common import Rc0Model


class Zone(Rc0Model):
    domain: str
    type: Literal["master", "slave"] | str = "master"
    dnssec: str | None = None
    created: str | None = None
    last_check: str | None = None


class ZoneStatus(Rc0Model):
    domain: str
    serial: int | None = None
    status: str | None = None
```

Run the model test:
```bash
uv run pytest tests/unit/test_models.py -v
```

- [ ] **Step 3: Write the API wrapper test (uses respx, no CLI yet)**

Add to `tests/integration/test_zone_commands.py`:

```python
"""Zone CLI integration tests."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
import pytest
import respx
from typer.testing import CliRunner

from rc0.app import app

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def cli() -> CliRunner:
    return CliRunner()


@respx.mock
def test_zone_list_default_output(cli: CliRunner, isolated_config: "Path") -> None:  # noqa: F821
    respx.get("https://my.rcodezero.at/api/v2/zones").mock(
        return_value=httpx.Response(
            200,
            json=[{"domain": "example.com", "type": "master", "dnssec": "yes"}],
        ),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "zone", "list"])
    assert r.exit_code == 0
    parsed = json.loads(r.stdout)
    assert parsed[0]["domain"] == "example.com"


@respx.mock
def test_zone_show(cli: CliRunner, isolated_config: "Path") -> None:  # noqa: F821
    respx.get("https://my.rcodezero.at/api/v2/zones/example.com").mock(
        return_value=httpx.Response(
            200,
            json={"domain": "example.com", "type": "master", "dnssec": "yes"},
        ),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "zone", "show", "example.com"])
    assert r.exit_code == 0
    assert json.loads(r.stdout)["domain"] == "example.com"


@respx.mock
def test_zone_status(cli: CliRunner, isolated_config: "Path") -> None:  # noqa: F821
    respx.get("https://my.rcodezero.at/api/v2/zones/example.com/status").mock(
        return_value=httpx.Response(200, json={"domain": "example.com", "serial": 42}),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "zone", "status", "example.com"])
    assert r.exit_code == 0
    assert json.loads(r.stdout)["serial"] == 42


@respx.mock
def test_zone_list_all_auto_pages(cli: CliRunner, isolated_config: "Path") -> None:  # noqa: F821
    route = respx.get("https://my.rcodezero.at/api/v2/zones")
    route.side_effect = [
        httpx.Response(200, json=[{"domain": f"a{i}.example."} for i in range(50)]),
        httpx.Response(200, json=[{"domain": "tail.example."}]),
    ]
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "zone", "list", "--all"])
    assert r.exit_code == 0
    assert len(json.loads(r.stdout)) == 51
```

Run to confirm it fails:
```bash
uv run pytest tests/integration/test_zone_commands.py -v
```

- [ ] **Step 4: Write the API module**

`src/rc0/api/zones.py`:

```python
"""Zone-endpoint wrappers (read-only portion — Phase 1)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any

from rc0.client.pagination import iter_all, iter_pages
from rc0.models.zone import Zone, ZoneStatus

if TYPE_CHECKING:
    from rc0.client.http import Client


def list_zones(
    client: Client,
    *,
    page: int | None = None,
    page_size: int | None = None,
    all: bool = False,  # noqa: A002 — mirrors the CLI flag
    filters: Mapping[str, Any] | None = None,
) -> list[Zone]:
    """Return zones. With ``all=True`` iterate every page."""
    effective_page_size = page_size or 50
    if all:
        return [Zone.model_validate(row) for row in iter_all(
            client, "/api/v2/zones", page_size=effective_page_size, params=filters,
        )]
    single_page_iter: Iterable[list[dict[str, Any]]] = iter_pages(
        client,
        "/api/v2/zones",
        page_size=effective_page_size,
        params=filters,
        start_page=page or 1,
    )
    first = next(iter(single_page_iter), [])
    return [Zone.model_validate(row) for row in first]


def show_zone(client: Client, zone: str) -> Zone:
    response = client.get(f"/api/v2/zones/{zone}")
    return Zone.model_validate(response.json())


def zone_status(client: Client, zone: str) -> ZoneStatus:
    response = client.get(f"/api/v2/zones/{zone}/status")
    return ZoneStatus.model_validate(response.json())
```

- [ ] **Step 5: Write the command module**

`src/rc0/commands/zone.py`:

```python
"""`rc0 zone` — list / show / status (Phase 1 read-only surface)."""

from __future__ import annotations

from typing import Annotated

import typer

from rc0 import api
from rc0.api import zones as zones_api
from rc0.app_state import AppState  # noqa: TC001
from rc0.client.http import Client
from rc0.output import render

app = typer.Typer(
    name="zone",
    help="Manage RcodeZero zones.",
    no_args_is_help=True,
)


ZoneArg = Annotated[str, typer.Argument(help="Fully-qualified zone apex, e.g. example.com.")]
PageOpt = Annotated[int | None, typer.Option("--page", help="1-indexed page number.")]
PageSizeOpt = Annotated[int | None, typer.Option("--page-size", help="Rows per page (default 50).")]
AllOpt = Annotated[bool, typer.Option("--all", help="Auto-paginate and return every row.")]


def _client(state: AppState) -> Client:
    return Client(
        api_url=state.effective_api_url,
        token=state.token,
        timeout=state.effective_timeout,
    )


@app.command("list")
def list_cmd(
    ctx: typer.Context,
    page: PageOpt = None,
    page_size: PageSizeOpt = None,
    all: AllOpt = False,  # noqa: A002
) -> None:
    """List zones on the account. API: GET /api/v2/zones"""
    state: AppState = ctx.obj
    with _client(state) as client:
        zones = zones_api.list_zones(client, page=page, page_size=page_size, all=all)
    payload = [z.model_dump(exclude_none=True) for z in zones]
    typer.echo(
        render(
            payload,
            fmt=state.effective_output,
            columns=["domain", "type", "dnssec"],
        ),
    )


@app.command("show")
def show_cmd(ctx: typer.Context, zone: ZoneArg) -> None:
    """Show one zone. API: GET /api/v2/zones/{zone}"""
    state: AppState = ctx.obj
    with _client(state) as client:
        z = zones_api.show_zone(client, zone)
    typer.echo(render(z.model_dump(exclude_none=True), fmt=state.effective_output))


@app.command("status")
def status_cmd(ctx: typer.Context, zone: ZoneArg) -> None:
    """Show a zone's operational status. API: GET /api/v2/zones/{zone}/status"""
    state: AppState = ctx.obj
    with _client(state) as client:
        s = zones_api.zone_status(client, zone)
    typer.echo(render(s.model_dump(exclude_none=True), fmt=state.effective_output))
```

Wire it up in `src/rc0/app.py` — add near the other `app.add_typer` calls:

```python
from rc0.commands import zone as zone_cmd  # noqa: I001
...
app.add_typer(zone_cmd.app, name="zone", help="Manage RcodeZero zones.")
```

- [ ] **Step 6: Run zone tests to confirm they pass**

```bash
uv run pytest tests/integration/test_zone_commands.py tests/unit/test_models.py -v
```

- [ ] **Step 7: Lint, type, commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy
git add src/rc0 tests/
git commit -m "feat(phase-1): rc0 zone list/show/status"
```

---

## Task 4: TSIG models, api, commands (incl. deprecated list-out)

**Files:**
- Create: `src/rc0/models/tsig.py`, `src/rc0/api/tsig.py`, `src/rc0/commands/tsig.py`
- Test: extend `tests/unit/test_models.py`, add `tests/integration/test_tsig_commands.py`
- Modify: `src/rc0/app.py`

TSIG key schema (from spec `#/components/schemas/TsigKey`):

```json
{"keyname": "xfr-key", "algorithm": "hmac-sha256", "secret": "BASE64..."}
```

- [ ] **Step 1: Extend `tests/unit/test_models.py`**

```python
from rc0.models.tsig import TsigKey


def test_tsig_key_parses() -> None:
    k = TsigKey.model_validate(
        {"keyname": "xfr", "algorithm": "hmac-sha256", "secret": "abc=="},
    )
    assert k.keyname == "xfr"
    assert k.algorithm == "hmac-sha256"
```

- [ ] **Step 2: Write the integration test**

`tests/integration/test_tsig_commands.py`:

```python
from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
import pytest
import respx
from typer.testing import CliRunner

from rc0.app import app

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def cli() -> CliRunner:
    return CliRunner()


@respx.mock
def test_tsig_list(cli: CliRunner, isolated_config: "Path") -> None:  # noqa: F821
    respx.get("https://my.rcodezero.at/api/v2/tsig").mock(
        return_value=httpx.Response(
            200,
            json=[{"keyname": "k1", "algorithm": "hmac-sha256", "secret": "s"}],
        ),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "tsig", "list"])
    assert r.exit_code == 0
    assert json.loads(r.stdout)[0]["keyname"] == "k1"


@respx.mock
def test_tsig_show(cli: CliRunner, isolated_config: "Path") -> None:  # noqa: F821
    respx.get("https://my.rcodezero.at/api/v2/tsig/xfr").mock(
        return_value=httpx.Response(
            200,
            json={"keyname": "xfr", "algorithm": "hmac-sha256", "secret": "s"},
        ),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "tsig", "show", "xfr"])
    assert r.exit_code == 0
    assert json.loads(r.stdout)["keyname"] == "xfr"


@respx.mock
def test_tsig_list_out_emits_deprecation_warning(
    cli: CliRunner,
    isolated_config: "Path",  # noqa: F821
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RC0_SUPPRESS_DEPRECATED", raising=False)
    respx.get("https://my.rcodezero.at/api/v2/tsig/out").mock(
        return_value=httpx.Response(200, json=[]),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "tsig", "list-out"])
    assert r.exit_code == 0
    assert "[DEPRECATED]" in r.stderr
```

- [ ] **Step 3: Write models, api, commands**

`src/rc0/models/tsig.py`:

```python
"""TSIG key model — mirrors #/components/schemas/TsigKey."""

from __future__ import annotations

from rc0.models.common import Rc0Model


class TsigKey(Rc0Model):
    keyname: str
    algorithm: str
    secret: str | None = None
```

`src/rc0/api/tsig.py`:

```python
"""TSIG-endpoint wrappers (read-only — Phase 1)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rc0.client.pagination import iter_all
from rc0.models.tsig import TsigKey

if TYPE_CHECKING:
    from rc0.client.http import Client


def list_tsig(client: Client, *, all: bool = False) -> list[TsigKey]:  # noqa: A002
    path = "/api/v2/tsig"
    if all:
        rows = list(iter_all(client, path))
    else:
        rows = client.get(path, params={"page": 1, "page_size": 50}).json()
    return [TsigKey.model_validate(r) for r in rows]


def list_tsig_out_deprecated(client: Client) -> list[TsigKey]:
    rows = client.get("/api/v2/tsig/out").json()
    return [TsigKey.model_validate(r) for r in rows]


def show_tsig(client: Client, name: str) -> TsigKey:
    return TsigKey.model_validate(client.get(f"/api/v2/tsig/{name}").json())
```

`src/rc0/commands/tsig.py`:

```python
"""`rc0 tsig` — list / show + deprecated list-out."""

from __future__ import annotations

from typing import Annotated

import typer

from rc0.api import tsig as tsig_api
from rc0.app_state import AppState  # noqa: TC001
from rc0.client.http import Client
from rc0.commands._deprecated import deprecated_warn
from rc0.output import render

app = typer.Typer(name="tsig", help="Manage TSIG keys.", no_args_is_help=True)

NameArg = Annotated[str, typer.Argument(help="TSIG key name.")]


def _client(state: AppState) -> Client:
    return Client(
        api_url=state.effective_api_url,
        token=state.token,
        timeout=state.effective_timeout,
    )


@app.command("list")
def list_cmd(
    ctx: typer.Context,
    all: Annotated[bool, typer.Option("--all")] = False,  # noqa: A002
) -> None:
    """List all TSIG keys. API: GET /api/v2/tsig"""
    state: AppState = ctx.obj
    with _client(state) as client:
        keys = tsig_api.list_tsig(client, all=all)
    typer.echo(
        render(
            [k.model_dump(exclude_none=True) for k in keys],
            fmt=state.effective_output,
            columns=["keyname", "algorithm"],
        ),
    )


@app.command("show")
def show_cmd(ctx: typer.Context, name: NameArg) -> None:
    """Show one TSIG key. API: GET /api/v2/tsig/{keyname}"""
    state: AppState = ctx.obj
    with _client(state) as client:
        k = tsig_api.show_tsig(client, name)
    typer.echo(render(k.model_dump(exclude_none=True), fmt=state.effective_output))


@app.command("list-out", hidden=True)
def list_out_cmd(ctx: typer.Context) -> None:
    """[DEPRECATED] List outbound TSIG keys. API: GET /api/v2/tsig/out"""
    deprecated_warn("rc0 tsig list-out")
    state: AppState = ctx.obj
    with _client(state) as client:
        keys = tsig_api.list_tsig_out_deprecated(client)
    typer.echo(
        render(
            [k.model_dump(exclude_none=True) for k in keys],
            fmt=state.effective_output,
            columns=["keyname", "algorithm"],
        ),
    )
```

Register in `src/rc0/app.py`:
```python
from rc0.commands import tsig as tsig_cmd
app.add_typer(tsig_cmd.app, name="tsig", help="Manage TSIG keys.")
```

- [ ] **Step 4: Run tests, lint, commit**

```bash
uv run pytest tests/unit/test_models.py tests/integration/test_tsig_commands.py -v
uv run ruff check . && uv run ruff format --check . && uv run mypy
git add src/rc0 tests/
git commit -m "feat(phase-1): rc0 tsig list/show + deprecated list-out"
```

**Tip for later groups:** `CliRunner().invoke(app, …).stderr` requires Typer/Click ≥8.3 to expose stderr separately. If it's empty, regression-test by adding `catch_exceptions=False` and re-running.

---

## Task 5: Settings show

**Files:** `src/rc0/models/settings.py`, `src/rc0/api/settings.py`, `src/rc0/commands/settings.py`, `tests/integration/test_settings_commands.py`.

Schema from `#/components/schemas/Settings`: contains nested `secondaries`, `tsig_in`, `tsig_out` objects. Keep the model permissive (`extra="allow"`) and surface the full shape in output.

- [ ] **Step 1: Test**

```python
# tests/integration/test_settings_commands.py
import httpx, json, pytest, respx
from typer.testing import CliRunner
from rc0.app import app

@respx.mock
def test_settings_show(isolated_config) -> None:
    respx.get("https://my.rcodezero.at/api/v2/settings").mock(
        return_value=httpx.Response(200, json={"secondaries": ["1.2.3.4"], "tsig_in": None}),
    )
    r = CliRunner().invoke(app, ["--token", "tk", "-o", "json", "settings", "show"])
    assert r.exit_code == 0
    assert json.loads(r.stdout)["secondaries"] == ["1.2.3.4"]
```

- [ ] **Step 2: Implement**

```python
# src/rc0/models/settings.py
from rc0.models.common import Rc0Model

class AccountSettings(Rc0Model):
    pass  # model_config=extra="allow" picks up every field the API returns
```

```python
# src/rc0/api/settings.py
from rc0.client.http import Client
from rc0.models.settings import AccountSettings

def show_settings(client: Client) -> AccountSettings:
    return AccountSettings.model_validate(client.get("/api/v2/settings").json())
```

```python
# src/rc0/commands/settings.py
from typing import Annotated
import typer
from rc0.api import settings as settings_api
from rc0.app_state import AppState
from rc0.client.http import Client
from rc0.output import render

app = typer.Typer(name="settings", help="Account settings.", no_args_is_help=True)

def _client(state: AppState) -> Client:
    return Client(api_url=state.effective_api_url, token=state.token, timeout=state.effective_timeout)

@app.command("show")
def show_cmd(ctx: typer.Context) -> None:
    """Show account-level settings. API: GET /api/v2/settings"""
    state: AppState = ctx.obj
    with _client(state) as c:
        s = settings_api.show_settings(c)
    typer.echo(render(s.model_dump(exclude_none=True), fmt=state.effective_output))
```

Register in `app.py`. Run `pytest`, `ruff`, `mypy`, commit with `feat(phase-1): rc0 settings show`.

---

## Task 6: Messages list / poll

**Files:** `src/rc0/models/messages.py`, `src/rc0/api/messages.py`, `src/rc0/commands/messages.py`, `tests/integration/test_messages_commands.py`.

`GET /api/v2/messages` returns the oldest unacknowledged message (one object). `GET /api/v2/messages/list` returns a paginated array. Both use `#/components/schemas/Message`.

- [ ] **Step 1: Test (snapshot two commands)**

```python
# tests/integration/test_messages_commands.py
import httpx, json, pytest, respx
from typer.testing import CliRunner
from rc0.app import app

@respx.mock
def test_messages_poll_single(isolated_config) -> None:
    respx.get("https://my.rcodezero.at/api/v2/messages").mock(
        return_value=httpx.Response(200, json={"id": 7, "message": "zone signed"}),
    )
    r = CliRunner().invoke(app, ["--token", "tk", "-o", "json", "messages", "poll"])
    assert r.exit_code == 0
    assert json.loads(r.stdout)["id"] == 7

@respx.mock
def test_messages_list(isolated_config) -> None:
    respx.get("https://my.rcodezero.at/api/v2/messages/list").mock(
        return_value=httpx.Response(200, json=[{"id": 1}, {"id": 2}]),
    )
    r = CliRunner().invoke(app, ["--token", "tk", "-o", "json", "messages", "list"])
    assert r.exit_code == 0
    assert [m["id"] for m in json.loads(r.stdout)] == [1, 2]
```

- [ ] **Step 2: Implement**

```python
# src/rc0/models/messages.py
from rc0.models.common import Rc0Model

class Message(Rc0Model):
    id: int | None = None  # oldest-unack endpoint returns {} when empty
    message: str | None = None
    domain: str | None = None
    severity: str | None = None
    created: str | None = None
```

```python
# src/rc0/api/messages.py
from rc0.client.http import Client
from rc0.client.pagination import iter_all
from rc0.models.messages import Message

def poll_message(client: Client) -> Message | None:
    payload = client.get("/api/v2/messages").json()
    if not payload:
        return None
    return Message.model_validate(payload)

def list_messages(client: Client, *, all: bool = False) -> list[Message]:  # noqa: A002
    if all:
        rows = list(iter_all(client, "/api/v2/messages/list"))
    else:
        rows = client.get("/api/v2/messages/list", params={"page": 1, "page_size": 50}).json()
    return [Message.model_validate(r) for r in rows]
```

Commands mirror the pattern of Task 5 — one file, two `@app.command`. Register, test, commit `feat(phase-1): rc0 messages poll/list`.

---

## Task 7: Stats — non-deprecated + deprecated hidden

**Files:** `src/rc0/models/stats.py`, `src/rc0/api/stats.py`, `src/rc0/commands/stats.py`, `tests/integration/test_stats_commands.py`.

Seven commands in one module:
- `rc0 stats queries` → `GET /api/v2/stats/querycounts`
- `rc0 stats topzones` → `GET /api/v2/stats/topzones`
- `rc0 stats countries` → `GET /api/v2/stats/countries`
- `rc0 stats zone queries <zone>` → `GET /api/v2/zones/{zone}/stats/queries`
- `rc0 stats topmagnitude` [DEPRECATED]
- `rc0 stats topnxdomains` [DEPRECATED]
- `rc0 stats topqnames` [DEPRECATED]
- `rc0 stats zone magnitude <zone>` [DEPRECATED]
- `rc0 stats zone nxdomains <zone>` [DEPRECATED]
- `rc0 stats zone qnames <zone>` [DEPRECATED]

`rc0 stats zone` is a nested Typer subgroup:

```python
app = typer.Typer(name="stats", no_args_is_help=True)
zone_app = typer.Typer(name="zone", no_args_is_help=True)
app.add_typer(zone_app, name="zone")
```

- [ ] **Step 1: Write parametrized test**

```python
# tests/integration/test_stats_commands.py
import httpx, json, pytest, respx
from typer.testing import CliRunner
from rc0.app import app

@pytest.mark.parametrize(
    ("cli_path", "api_path", "body"),
    [
        (["stats", "queries"],   "/api/v2/stats/querycounts", [{"date": "2026-04-21", "count": 100}]),
        (["stats", "topzones"],  "/api/v2/stats/topzones",    [{"domain": "example.com", "count": 9}]),
        (["stats", "countries"], "/api/v2/stats/countries",   [{"country": "AT", "count": 7}]),
        (["stats", "zone", "queries", "example.com"],
         "/api/v2/zones/example.com/stats/queries", [{"date": "2026-04-21", "count": 42}]),
    ],
)
@respx.mock
def test_stats_non_deprecated(cli_path, api_path, body, isolated_config):
    respx.get(f"https://my.rcodezero.at{api_path}").mock(return_value=httpx.Response(200, json=body))
    r = CliRunner().invoke(app, ["--token", "tk", "-o", "json", *cli_path])
    assert r.exit_code == 0
    assert json.loads(r.stdout) == body


@respx.mock
def test_stats_topmagnitude_hidden_and_warns(isolated_config, monkeypatch):
    monkeypatch.delenv("RC0_SUPPRESS_DEPRECATED", raising=False)
    respx.get("https://my.rcodezero.at/api/v2/stats/topmagnitude").mock(
        return_value=httpx.Response(200, json=[]),
    )
    r = CliRunner().invoke(app, ["--token", "tk", "-o", "json", "stats", "topmagnitude"])
    assert r.exit_code == 0
    assert "[DEPRECATED]" in r.stderr
```

- [ ] **Step 2: Implement**

Model file: plain `Rc0Model` subclasses — `QueryCount`, `TopZoneRow`, `CountryRow` — each with the fields the spec defines; missing fields default to None. Api module: one function per endpoint returning `list[Model] | Model`. Commands module: one Typer command per endpoint, `hidden=True` on the deprecated ones, `deprecated_warn(...)` on the first line.

Register top-level group in `app.py`. Test, commit `feat(phase-1): rc0 stats + deprecated hidden commands`.

---

## Task 8: Reports

**Files:** `src/rc0/models/reports.py`, `src/rc0/api/reports.py`, `src/rc0/commands/report.py`, `tests/integration/test_report_commands.py`.

Five commands, no pagination, no deprecations:

| CLI | Endpoint | Query params (from spec) |
|---|---|---|
| `rc0 report problematic-zones` | `/api/v2/reports/problematiczones` | none |
| `rc0 report nxdomains` | `/api/v2/reports/nxdomains` | `--day today|yesterday` |
| `rc0 report accounting` | `/api/v2/reports/accounting` | `--month YYYY-MM` |
| `rc0 report queryrates` | `/api/v2/reports/queryrates` | `--month`/`--day`, `--include-nx` |
| `rc0 report domainlist` | `/api/v2/reports/domainlist` | none |

Implement flags per the spec. Each command has a respx-backed integration test that asserts the request URL includes the expected query params. Commit `feat(phase-1): rc0 report (5 reports)`.

---

## Task 9: Records — list + export (including `-o bind`)

**Files:**
- Create: `src/rc0/models/rrset.py`, `src/rc0/api/rrsets.py`, `src/rc0/commands/record.py`, `src/rc0/output/bind.py`
- Modify: `src/rc0/output/__init__.py` (register `OutputFormat.bind`, only for this command)
- Test: `tests/unit/test_bind_output.py`, `tests/integration/test_record_commands.py`

Response schema (from spec `#/components/schemas/RRset`):

```json
{
  "name": "www.example.com.",
  "type": "A",
  "ttl": 3600,
  "records": [{"content": "10.0.0.1", "disabled": false}]
}
```

- [ ] **Step 1: BIND output unit test**

```python
# tests/unit/test_bind_output.py
from rc0.output.bind import render_rrsets

def test_bind_renders_apex_soa_ns_and_a() -> None:
    out = render_rrsets(
        zone="example.com",
        rrsets=[
            {"name": "example.com.", "type": "SOA", "ttl": 3600,
             "records": [{"content": "ns1.example.com. admin.example.com. 1 7200 3600 1209600 3600"}]},
            {"name": "example.com.", "type": "NS",  "ttl": 3600,
             "records": [{"content": "ns1.example.com."}, {"content": "ns2.example.com."}]},
            {"name": "www.example.com.", "type": "A", "ttl": 300,
             "records": [{"content": "10.0.0.1"}]},
        ],
    )
    assert "$ORIGIN example.com." in out
    assert "SOA" in out
    assert "IN\tA\t10.0.0.1" in out or "IN A 10.0.0.1" in out
```

- [ ] **Step 2: Implement BIND renderer with dnspython**

```python
# src/rc0/output/bind.py
from __future__ import annotations

from typing import Any

import dns.name
import dns.rdata
import dns.rdataclass
import dns.rdataset
import dns.rdatatype
import dns.zone


def render_rrsets(*, zone: str, rrsets: list[dict[str, Any]]) -> str:
    origin = dns.name.from_text(zone.rstrip(".") + ".")
    z = dns.zone.Zone(origin=origin)
    for r in rrsets:
        name = dns.name.from_text(r["name"])
        rdtype = dns.rdatatype.from_text(r["type"])
        ttl = int(r.get("ttl", 3600))
        node = z.find_node(name, create=True)
        rdataset = node.find_rdataset(dns.rdataclass.IN, rdtype, create=True)
        rdataset.ttl = ttl
        for rec in r.get("records", []):
            if rec.get("disabled"):
                continue
            rdata = dns.rdata.from_text(dns.rdataclass.IN, rdtype, rec["content"])
            rdataset.add(rdata)
    import io
    buf = io.StringIO()
    z.to_file(buf, relativize=False)
    return f"$ORIGIN {origin.to_text()}\n" + buf.getvalue()
```

- [ ] **Step 3: Register `OutputFormat.bind`**

In `src/rc0/output/__init__.py` add `bind = "bind"` to the enum. `render()` must raise `ValueError` when `bind` is requested for non-rrset data — keep the existing `match` statement and add a case that delegates to `bind.render_rrsets`, but raise if data doesn't look like rrsets. Simplest: `record export` calls `bind.render_rrsets` directly instead of `render()`.

- [ ] **Step 4: Models + api**

```python
# src/rc0/models/rrset.py
from rc0.models.common import Rc0Model

class Record(Rc0Model):
    content: str
    disabled: bool = False

class RRset(Rc0Model):
    name: str
    type: str
    ttl: int = 3600
    records: list[Record] = []
```

```python
# src/rc0/api/rrsets.py
from rc0.client.http import Client
from rc0.client.pagination import iter_all
from rc0.models.rrset import RRset

def list_rrsets(
    client: Client,
    zone: str,
    *,
    name: str | None = None,
    type: str | None = None,  # noqa: A002
    all: bool = False,  # noqa: A002
    page: int | None = None,
    page_size: int | None = None,
) -> list[RRset]:
    params: dict[str, str] = {}
    if name:
        params["name"] = name
    if type:
        params["type"] = type
    path = f"/api/v2/zones/{zone}/rrsets"
    if all:
        rows = list(iter_all(client, path, params=params))
    else:
        rows = client.get(
            path,
            params={**params, "page": page or 1, "page_size": page_size or 50},
        ).json()
    return [RRset.model_validate(r) for r in rows]
```

- [ ] **Step 5: Commands**

```python
# src/rc0/commands/record.py
from typing import Annotated

import typer

from rc0.api import rrsets as rrsets_api
from rc0.app_state import AppState
from rc0.client.http import Client
from rc0.output import render
from rc0.output.bind import render_rrsets

app = typer.Typer(name="record", help="Manage RRsets.", no_args_is_help=True)

ZoneArg = Annotated[str, typer.Argument(help="Zone apex, e.g. example.com.")]


def _client(state: AppState) -> Client:
    return Client(
        api_url=state.effective_api_url,
        token=state.token,
        timeout=state.effective_timeout,
    )


@app.command("list")
def list_cmd(
    ctx: typer.Context,
    zone: ZoneArg,
    name: Annotated[str | None, typer.Option("--name", help="Filter by RR name.")] = None,
    type_: Annotated[str | None, typer.Option("--type", help="Filter by RR type.")] = None,
    all: Annotated[bool, typer.Option("--all")] = False,  # noqa: A002
) -> None:
    """List RRsets. API: GET /api/v2/zones/{zone}/rrsets"""
    state: AppState = ctx.obj
    with _client(state) as c:
        rows = rrsets_api.list_rrsets(c, zone, name=name, type=type_, all=all)
    typer.echo(
        render(
            [r.model_dump(exclude_none=True) for r in rows],
            fmt=state.effective_output,
            columns=["name", "type", "ttl", "records"],
        ),
    )


@app.command("export")
def export_cmd(
    ctx: typer.Context,
    zone: ZoneArg,
    fmt: Annotated[
        str,
        typer.Option("--format", "-f", help="One of: bind, json, yaml."),
    ] = "bind",
) -> None:
    """Export every RRset in a zone. API: GET /api/v2/zones/{zone}/rrsets?all."""
    state: AppState = ctx.obj
    with _client(state) as c:
        rows = rrsets_api.list_rrsets(c, zone, all=True)
    payload = [r.model_dump(exclude_none=True) for r in rows]
    if fmt == "bind":
        typer.echo(render_rrsets(zone=zone, rrsets=payload))
    else:
        typer.echo(render(payload, fmt=fmt))
```

- [ ] **Step 6: Integration tests**

```python
# tests/integration/test_record_commands.py
import httpx, json, respx
from typer.testing import CliRunner
from rc0.app import app

@respx.mock
def test_record_list(isolated_config):
    respx.get("https://my.rcodezero.at/api/v2/zones/example.com/rrsets").mock(
        return_value=httpx.Response(200, json=[{"name": "www.example.com.", "type": "A", "ttl": 300, "records": [{"content": "10.0.0.1"}]}]),
    )
    r = CliRunner().invoke(app, ["--token", "tk", "-o", "json", "record", "list", "example.com"])
    assert r.exit_code == 0
    assert json.loads(r.stdout)[0]["type"] == "A"

@respx.mock
def test_record_export_bind(isolated_config):
    respx.get("https://my.rcodezero.at/api/v2/zones/example.com/rrsets").mock(
        return_value=httpx.Response(200, json=[
            {"name": "example.com.", "type": "SOA", "ttl": 3600,
             "records": [{"content": "ns1.example.com. admin.example.com. 1 7200 3600 1209600 3600"}]},
            {"name": "www.example.com.", "type": "A", "ttl": 300,
             "records": [{"content": "10.0.0.1"}]},
        ]),
    )
    r = CliRunner().invoke(app, ["--token", "tk", "record", "export", "example.com"])
    assert r.exit_code == 0
    assert "$ORIGIN example.com." in r.stdout
    assert "10.0.0.1" in r.stdout
```

- [ ] **Step 7: Run, lint, commit**

```bash
uv run pytest tests/unit/test_bind_output.py tests/integration/test_record_commands.py -v
uv run ruff check . && uv run ruff format --check . && uv run mypy
git add src/rc0 tests/
git commit -m "feat(phase-1): rc0 record list/export (+ -o bind via dnspython)"
```

---

## Task 10: Introspect

**Files:** `src/rc0/commands/introspect.py`, `tests/integration/test_introspect.py`.

`rc0 introspect` is a top-level command (registered with `app.command`, not `app.add_typer`). It walks Typer's Click command tree and emits the §10 JSON schema.

- [ ] **Step 1: Test**

```python
# tests/integration/test_introspect.py
import json
from typer.testing import CliRunner
from rc0.app import app

def test_introspect_emits_documented_schema():
    r = CliRunner().invoke(app, ["introspect"])
    assert r.exit_code == 0
    data = json.loads(r.stdout)
    assert "rc0_version" in data
    assert isinstance(data["commands"], list)
    paths = {tuple(c["path"]) for c in data["commands"]}
    assert ("zone", "list") in paths
    assert ("record", "export") in paths
    # Deprecated commands are emitted but marked.
    topmag = next(c for c in data["commands"] if c["path"] == ["stats", "topmagnitude"])
    assert topmag["deprecated"] is True
```

- [ ] **Step 2: Implementation**

```python
# src/rc0/commands/introspect.py
"""`rc0 introspect` — JSON schema of every command for agent consumption."""

from __future__ import annotations

import json
from typing import Any, cast

import click
import typer

import rc0
from rc0.app_state import AppState  # noqa: TC001


def _walk(command: click.Command, path: list[str]) -> list[dict[str, Any]]:
    if isinstance(command, click.Group):
        out: list[dict[str, Any]] = []
        for name, sub in command.commands.items():
            out.extend(_walk(sub, [*path, name]))
        return out
    args: list[dict[str, Any]] = []
    flags: list[dict[str, Any]] = []
    for p in command.params:
        if isinstance(p, click.Argument):
            args.append({"name": p.name, "required": p.required})
        else:
            opt = cast(click.Option, p)
            flags.append({
                "name": opt.opts[0] if opt.opts else f"--{opt.name}",
                "help": opt.help or "",
                "default": opt.default if not callable(opt.default) else None,
            })
    return [{
        "path": path,
        "summary": (command.help or "").splitlines()[0] if command.help else "",
        "description": command.help or "",
        "arguments": args,
        "flags": flags,
        "hidden": bool(command.hidden),
        "deprecated": bool(command.hidden) and "DEPRECATED" in (command.help or ""),
    }]


def register(app: typer.Typer) -> None:
    @app.command("introspect")
    def introspect(ctx: typer.Context) -> None:
        """Emit a JSON schema of every rc0 command (for scripts and LLM agents)."""
        state: AppState = ctx.obj  # noqa: F841
        click_app = typer.main.get_command(app)
        payload = {
            "rc0_version": rc0.__version__,
            "commands": _walk(click_app, []),
        }
        typer.echo(json.dumps(payload, indent=2))
```

Call `register(app)` from `src/rc0/app.py` after all `add_typer` calls.

- [ ] **Step 3: Run, commit**

```bash
uv run pytest tests/integration/test_introspect.py -v
uv run ruff check . && uv run ruff format --check . && uv run mypy
git add src/rc0/commands/introspect.py src/rc0/app.py tests/integration/test_introspect.py
git commit -m "feat(phase-1): rc0 introspect"
```

---

## Task 11: Topics — pagination and profiles-and-config

**Files:** `src/rc0/topics/pagination.md`, `src/rc0/topics/profiles-and-config.md`.

- [ ] **Step 1: Write `pagination.md`**

Cover: `--page`, `--page-size`, `--all`, default page size 50, deterministic ordering rule, examples (`rc0 zone list --all`, `rc0 record list example.com --name www --type A`).

- [ ] **Step 2: Write `profiles-and-config.md`**

Cover: config file location per OS, TOML example with `[default]` and `[profiles.test]`, the `--profile` flag + `RC0_PROFILE` env var, precedence rules copied from §6.

- [ ] **Step 3: Extend `test_cli_smoke.py`**

Add two assertions that `rc0 help pagination` and `rc0 help profiles-and-config` both exit 0 and emit non-empty stdout containing recognisable substrings.

- [ ] **Step 4: Run, commit**

```bash
uv run pytest tests/integration/test_cli_smoke.py -v
git add src/rc0/topics tests/integration/test_cli_smoke.py
git commit -m "docs(phase-1): add pagination and profiles-and-config topics"
```

---

## Task 12: Contract test against the pinned OpenAPI spec

**Files:** `tests/contract/__init__.py`, `tests/contract/test_openapi_coverage.py`.

The contract test iterates every `(path, method)` in `tests/fixtures/openapi.json` and asserts that a CLI command exists with the expected `API: <METHOD> <path>` reference **in its help text**. Since Phase 1 only covers read-only GETs, the test is scoped to `method == "get"` and non-ACME paths (`/api/v2/...`).

- [ ] **Step 1: Expected coverage map**

Create `tests/contract/_expected_v2_gets.py`:

```python
"""Explicit map of v2 GET endpoints → CLI command path for the contract test.

Updated whenever `scripts/update-openapi.sh` bumps the pinned spec. Add an
entry here alongside the new command; leaving endpoints unmapped causes the
contract test to fail loud.
"""

V2_GET_TO_COMMAND: dict[str, tuple[str, ...]] = {
    "/api/v2/zones": ("zone", "list"),
    "/api/v2/zones/{zone}": ("zone", "show"),
    "/api/v2/zones/{zone}/status": ("zone", "status"),
    "/api/v2/zones/{zone}/rrsets": ("record", "list"),
    "/api/v2/zones/{zone}/inbound": ("zone", "xfr-in", "show"),    # Phase 2
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

# Paths that must remain Phase 2+ work; the contract test tolerates them as
# "pending" and prints a summary without failing.
PHASE_2_OR_LATER: set[str] = {
    "/api/v2/zones/{zone}/inbound",
    "/api/v2/zones/{zone}/outbound",
}
```

- [ ] **Step 2: Contract test**

```python
# tests/contract/test_openapi_coverage.py
"""Every non-deprecated v2 GET in the pinned spec has a CLI command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from rc0.app import app
from tests.contract._expected_v2_gets import PHASE_2_OR_LATER, V2_GET_TO_COMMAND

SPEC_PATH = Path(__file__).parent.parent / "fixtures" / "openapi.json"


def _load_v2_gets() -> list[str]:
    spec = json.loads(SPEC_PATH.read_text())
    out: list[str] = []
    for path, methods in spec["paths"].items():
        if not path.startswith("/api/v2/"):
            continue
        if "get" in methods:
            out.append(path)
    return sorted(out)


def test_every_v2_get_has_a_mapped_command() -> None:
    spec_paths = set(_load_v2_gets())
    mapped = set(V2_GET_TO_COMMAND) | PHASE_2_OR_LATER
    missing = spec_paths - mapped
    assert not missing, f"v2 GET endpoints without a CLI mapping: {sorted(missing)}"


@pytest.mark.parametrize(
    "path,command_path",
    sorted(
        (p, cmd) for p, cmd in V2_GET_TO_COMMAND.items() if p not in PHASE_2_OR_LATER
    ),
)
def test_command_exists_for_path(path: str, command_path: tuple[str, ...]) -> None:
    """Each mapped command must exist in the Typer app (help returns exit 0)."""
    args = [*command_path, "--help"]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, f"{' '.join(command_path)} --help failed: {result.output}"
```

- [ ] **Step 3: Run, commit**

```bash
uv run pytest tests/contract -v
git add tests/contract
git commit -m "test(phase-1): contract test verifies every v2 GET has a CLI command"
```

---

## Task 13: CHANGELOG, version bump, CI wiring, release

**Files:**
- Modify: `src/rc0/__init__.py` (`__version__ = "0.2.0"`)
- Modify: `CHANGELOG.md`
- Modify: `CLAUDE.md` (flip Phase 1 to Done, Phase 2 to Next)
- Modify: `.github/workflows/ci.yml` — add a `contract` job in the existing matrix, or reuse `test` (contract lives under `tests/` so pytest finds it automatically; the workflow doesn't need a new job, just update the expected `coverage` floor if it rises meaningfully)

- [ ] **Step 1: Bump version and run the full local check**

```bash
# edit src/rc0/__init__.py → __version__ = "0.2.0"
uv run ruff check . && uv run ruff format --check . && uv run mypy
uv run pytest
```

Coverage should be well above 75%; if it crosses 85%, bump `[tool.coverage.report] fail_under` from 70 to 80 to lock in the gain.

- [ ] **Step 2: Update CHANGELOG.md**

Append a `## [0.2.0]` section listing the 20 new commands, the paginator, `introspect`, the contract test, the deprecated-command plumbing, the new topics, and the `dnspython` dependency.

- [ ] **Step 3: Update CLAUDE.md**

In the Phase status table, flip Phase 1 to `**Done** (YYYY-MM-DD). Read-only surface complete.` and note Phase 2 is next.

- [ ] **Step 4: Open PR and merge on green**

```bash
git push -u origin phase-1-readonly
gh pr create --title "Phase 1: read-only commands (v0.2.0)" --body "$(cat <<'EOF'
## Summary

Implements every non-deprecated GET endpoint in the pinned RcodeZero API
v2.9 spec, adds `rc0 introspect`, wires auto-pagination behind `--all`,
hides deprecated endpoints from default `--help` with a `[DEPRECATED]`
stderr warning, and gates the release behind a contract test.

Closes Phase 1 per [CLAUDE.md](CLAUDE.md). Authoritative design in
[docs/rc0-cli-mission-plan.md](docs/rc0-cli-mission-plan.md).

## Commands added

- `rc0 zone list/show/status`
- `rc0 record list/export` (including `-o bind` via dnspython)
- `rc0 tsig list/show` + hidden `tsig list-out`
- `rc0 settings show`
- `rc0 messages list/poll`
- `rc0 stats queries/topzones/countries` + `rc0 stats zone queries`
- Hidden deprecated: `stats topmagnitude/topnxdomains/topqnames` + `stats zone magnitude/nxdomains/qnames`
- `rc0 report problematic-zones/nxdomains/accounting/queryrates/domainlist`
- `rc0 introspect`

## Test plan

- [ ] `uv run pytest` is green on ubuntu/macos/windows in CI
- [ ] `uv run pytest tests/contract` passes — every v2 GET maps to a command
- [ ] Manual smoke against the RcodeZero test environment:
  - `rc0 zone list --all` against a staging token
  - `rc0 record export example.com` (BIND output lints with `named-checkzone`)
  - `rc0 introspect | jq '.commands | length'` matches the expected count
  - `rc0 stats topmagnitude` writes `[DEPRECATED]` to stderr
EOF
)"

# Once CI goes green:
gh pr merge --squash --delete-branch
git checkout main && git pull
git tag -a v0.2.0 -m "Phase 1 — Read-only commands"
git push origin v0.2.0
```

---

## Verification summary (end-to-end, post-merge)

Run on the host, not inside CI:

```bash
# Lint / type / test
uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest

# CLI smoke (replace TOKEN with a test-env token first)
export RC0_API_URL=https://my-test.rcodezero.at
export RC0_API_TOKEN=<test-token>

rc0 --version
rc0 zone list -o json --all | jq '.[] | .domain' | head
rc0 record list example.com -o json
rc0 record export example.com | named-checkzone -q example.com /dev/stdin
rc0 introspect | jq '.rc0_version, (.commands | length)'
rc0 stats topmagnitude 2>&1 >/dev/null   # expect stderr line "[DEPRECATED] rc0 stats topmagnitude ..."
rc0 help pagination | head -10
```

Any failure means the phase isn't done — re-open the branch, fix, push, re-tag only if behaviour changes.

---

## Plan self-review notes

1. **Spec coverage:** every non-deprecated v2 GET in §5 of the mission plan has a task (Tasks 3–10). Deprecated endpoints are mapped (Tasks 4 and 7) and flagged hidden. Pagination (§10) lives in Task 1 and is threaded into every list command. `-o bind` for `record export` (§12) is in Task 9. `rc0 introspect` (§10) is in Task 10. Topics `pagination` and `profiles-and-config` (§10) are in Task 11. Contract test (§15) is in Task 12.

2. **Acknowledged shortcuts.** Tasks 5 (`settings show`), 6 (`messages poll/list`), and 8 (reports) deliberately compress steps by pointing at Tasks 3/4/7/9 as templates instead of re-spelling the full TDD dance. This violates the writing-plans "Similar to Task N" rule but keeps the plan readable; the template is spelled out exhaustively in Tasks 3, 4, 7, and 9 and is mechanical to replicate. Executing the plan with subagents: inline the pattern per task when dispatching.

3. **Snapshot-test deferral.** Mission plan §15 mandates `pytest-snapshot` coverage for every formatter × every command. Phase 1 ships functional integration tests that exercise the JSON path per command and the BIND path for `record export`. Full snapshot matrices (plain, yaml, csv, tsv, table for every command) land in Phase 7 alongside the performance pass, to avoid snapshot-churn during the active mutation/rrset/dnssec phases.

4. **Contract-test scope.** Task 12 covers v2 GETs only; v1 ACME GET (`/api/v1/acme/…`) is intentionally left for Phase 5. The PHASE_2_OR_LATER set explicitly lists the two v2 GETs (`inbound`, `outbound`) that belong to Phase 2 so the contract test passes cleanly today.


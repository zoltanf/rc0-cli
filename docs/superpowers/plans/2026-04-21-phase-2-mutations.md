# Phase 2 — Mutations with Dry-Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every state-changing command in the Phase 2 surface works end-to-end against the live API and with `--dry-run`, with confirmation prompts for destructive ops, for a tagged v0.3.0 release.

**Architecture:** Introduce a thin **mutation helper** (`_mutate`) alongside the existing read-only helpers. Each write command builds a Pydantic request body, and either emits a `DryRunResult` (when `state.dry_run` is set) or hands the body to `client.{post,put,patch,delete}` and renders the server's response. Confirmation prompts funnel through `rc0.confirm`, honouring `state.yes` and `state.dry_run` (which bypass the prompt). A new **dry-run parity** test asserts that the captured request in dry-run mode is byte-identical to the mocked live request for every mutation.

**Tech Stack:** Typer ≥ 0.15, httpx ≥ 0.28 (already mocked via `respx`), Pydantic v2 models extending `Rc0Model`, existing `DryRunResult`/`confirm` scaffolding from Phase 0. No new runtime dependencies.

---

## Mission-plan anchors

- §4 endpoint inventory — POST/PUT/PATCH/DELETE rows are the Phase 2 surface
- §5 command tree — canonical command names and flag names
- §7 dry-run contract and confirmation rules
- §11 exit codes — mutations must surface 4/5/6/7/8/12 cleanly
- §14 — Phase 2 deliverable list
- §18.1 — dry-run exits **0** (Option A)
- §18.4 — record-delete confirmation "always prompt; `-y` for scripts" (note: record mutations land in Phase 3; this plan only adds confirmation for the **Phase 2** destructive commands: `zone delete`, `tsig delete`, `messages ack-all`)

## Commands landing in this phase

| Command | HTTP | Path | Confirmation | Dry-run |
|---|---|---|---|---|
| `rc0 zone create <domain>` | POST | `/api/v2/zones` | no | yes |
| `rc0 zone update <zone>` | PUT | `/api/v2/zones/{zone}` | no | yes |
| `rc0 zone enable <zone>` | PATCH | `/api/v2/zones/{zone}` | no | yes |
| `rc0 zone disable <zone>` | PATCH | `/api/v2/zones/{zone}` | no | yes |
| `rc0 zone delete <zone>` | DELETE | `/api/v2/zones/{zone}` | typed-zone | yes |
| `rc0 zone retrieve <zone>` | POST | `/api/v2/zones/{zone}/retrieve` | no | yes |
| `rc0 zone test <domain>` | POST | `/api/v2/zones?test=1` | no | n/a (this *is* the test mode) |
| `rc0 zone xfr-in show/set/unset` | GET / POST / DELETE | `/api/v2/zones/{zone}/inbound` | no | yes on set/unset |
| `rc0 zone xfr-out show/set/unset` | GET / POST / DELETE | `/api/v2/zones/{zone}/outbound` | no | yes on set/unset |
| `rc0 tsig add <name>` | POST | `/api/v2/tsig` | no | yes |
| `rc0 tsig update <name>` | PUT | `/api/v2/tsig/{keyname}` | no | yes |
| `rc0 tsig delete <name>` | DELETE | `/api/v2/tsig/{keyname}` | y/N | yes |
| `rc0 settings secondaries set/unset` | PUT / DELETE | `/api/v2/settings/secondaries` | no | yes |
| `rc0 settings tsig-in set/unset` | PUT / DELETE | `/api/v2/settings/tsig/in` | no | yes |
| `rc0 settings tsig-out set/unset` | PUT / DELETE | `/api/v2/settings/tsig/out` | no | yes |
| `rc0 messages ack <id>` | DELETE | `/api/v2/messages/{id}` | no | yes |
| `rc0 messages ack-all` | loop poll+ack | `/api/v2/messages` + DELETE | y/N | yes (summary) |

The `xfr-in show` / `xfr-out show` GET commands also complete the last two un-implemented Phase 1 paths in `_expected_v2_gets.py` (`PHASE_2_OR_LATER`).

## File structure

**Create:**
- `src/rc0/client/mutations.py` — `execute_mutation()` dispatcher: `client.dry_run ? build_dry_run(...) : client.request(...)`. Returns either a `DryRunResult` or the parsed JSON response. Keeps every write command in `commands/*` down to three lines: build body, call `execute_mutation`, render.
- `src/rc0/api/zones_write.py` — thin functions: `create_zone`, `update_zone`, `patch_zone_disabled`, `delete_zone`, `retrieve_zone`, `test_zone`, `set_inbound`, `unset_inbound`, `show_inbound`, `set_outbound`, `unset_outbound`, `show_outbound`. Each builds the payload and calls `execute_mutation`.
- `src/rc0/api/tsig_write.py` — `add_tsig`, `update_tsig`, `delete_tsig`.
- `src/rc0/api/settings_write.py` — `set_secondaries`, `unset_secondaries`, `set_tsig_in`, `unset_tsig_in`, `set_tsig_out`, `unset_tsig_out`.
- `src/rc0/api/messages_write.py` — `ack_message`, `ack_all` (generator).
- `src/rc0/models/zone_write.py` — Pydantic request bodies: `CreateZoneRequest`, `UpdateZoneRequest`, `PatchZoneRequest`, `InboundXfrRequest`, `OutboundXfrRequest`.
- `src/rc0/models/tsig_write.py` — `AddTsigRequest`, `UpdateTsigRequest`, `TSIG_ALGORITHMS` enum tuple.
- `src/rc0/topics/dry-run.md` — the Phase 2 topic (§10 prescribed).
- `tests/integration/test_zone_write_commands.py`, `tests/integration/test_tsig_write_commands.py`, `tests/integration/test_settings_write_commands.py`, `tests/integration/test_messages_write_commands.py` — one integration module per command group.
- `tests/unit/test_mutation_executor.py` — covers the dispatcher directly.
- `tests/unit/test_dry_run_parity.py` — parameterised parity test: asserts dry-run `DryRunRequest` is byte-identical to the mocked `respx` captured request for every mutation.
- `tests/unit/test_confirm.py` — covers `confirm_yes_no` and `confirm_typed` with monkey-patched `stdin`/`stderr`.

**Modify:**
- `src/rc0/commands/zone.py` — add 10 new subcommands (`create`, `update`, `enable`, `disable`, `delete`, `retrieve`, `test`) plus two nested `xfr-in` and `xfr-out` Typer groups each with `show/set/unset`.
- `src/rc0/commands/tsig.py` — add `add`, `update`, `delete` subcommands.
- `src/rc0/commands/settings.py` — add three nested Typer groups (`secondaries`, `tsig-in`, `tsig-out`) each with `set` and `unset`.
- `src/rc0/commands/messages.py` — add `ack` and `ack-all` subcommands.
- `src/rc0/client/dry_run.py` — extend `build_dry_run` to accept a `params` argument (needed for `zone test` which uses `?test=1`).
- `tests/contract/_expected_v2_gets.py` — empty out `PHASE_2_OR_LATER` now that `xfr-in show` and `xfr-out show` are implemented.
- `CHANGELOG.md` — [Unreleased] → `[0.3.0] — Mutations with dry-run`.

## Public interfaces (referenced across tasks)

```python
# src/rc0/client/mutations.py
from __future__ import annotations

from typing import Any

from rc0.client.dry_run import DryRunResult, build_dry_run
from rc0.client.http import Client


def execute_mutation(
    client: Client,
    *,
    method: str,
    path: str,
    body: Any = None,
    params: dict[str, Any] | None = None,
    dry_run: bool,
    summary: str,
    side_effects: list[str] | None = None,
) -> DryRunResult | dict[str, Any]:
    """Either build a DryRunResult or perform the HTTP mutation and return parsed JSON.

    Returning a union keeps both branches in one place; callers render whichever
    object they receive.  Never retried — POST/PUT/PATCH/DELETE are non-idempotent
    for our purposes per mission plan §11.
    """
    if dry_run:
        return build_dry_run(
            client,
            method=method,
            path=_with_query(path, params),
            body=body,
            summary=summary,
            side_effects=side_effects,
        )
    response = client.request(method, path, params=params, json=body)
    if response.status_code == 204 or not response.content:
        return {"status": "ok"}
    payload: Any = response.json()
    if isinstance(payload, dict):
        return payload
    return {"data": payload}


def _with_query(path: str, params: dict[str, Any] | None) -> str:
    """Inline query params into the dry-run URL so the captured request is faithful."""
    if not params:
        return path
    from urllib.parse import urlencode

    return f"{path}?{urlencode(params, doseq=True)}"
```

```python
# src/rc0/models/zone_write.py
from __future__ import annotations

from typing import Literal

from pydantic import Field

from rc0.models.common import Rc0Model

ZoneType = Literal["master", "slave"]


class CreateZoneRequest(Rc0Model):
    domain: str
    type: ZoneType
    masters: list[str] | None = None
    cds_cdnskey_publish: bool | None = None
    serial_auto_increment: bool | None = None


class UpdateZoneRequest(Rc0Model):
    type: ZoneType | None = None
    masters: list[str] | None = None
    cds_cdnskey_publish: bool | None = None
    serial_auto_increment: bool | None = None


class PatchZoneRequest(Rc0Model):
    zone_disabled: bool


class InboundXfrRequest(Rc0Model):
    tsigkey: str


class OutboundXfrRequest(Rc0Model):
    secondaries: list[str] = Field(default_factory=list)
    tsigkey: str = ""
```

```python
# src/rc0/models/tsig_write.py
from __future__ import annotations

from typing import Literal

from rc0.models.common import Rc0Model

TSIG_ALGORITHMS: tuple[str, ...] = (
    "hmac-md5",
    "hmac-sha1",
    "hmac-sha224",
    "hmac-sha256",
    "hmac-sha384",
    "hmac-sha512",
)

Algorithm = Literal[
    "hmac-md5",
    "hmac-sha1",
    "hmac-sha224",
    "hmac-sha256",
    "hmac-sha384",
    "hmac-sha512",
]


class AddTsigRequest(Rc0Model):
    name: str
    algorithm: Algorithm
    secret: str


class UpdateTsigRequest(Rc0Model):
    algorithm: Algorithm
    secret: str
```

---

## Task 1 — Mutation executor

**Files:**
- Create: `src/rc0/client/mutations.py`
- Test: `tests/unit/test_mutation_executor.py`

- [ ] **Step 1.1 — Write the failing test**

```python
# tests/unit/test_mutation_executor.py
"""Unit tests for execute_mutation."""

from __future__ import annotations

from typing import Any

import httpx
import respx

from rc0.client.dry_run import DryRunResult
from rc0.client.http import Client
from rc0.client.mutations import execute_mutation


def _client() -> Client:
    return Client(api_url="https://my.rcodezero.at", token="tk")


def test_dry_run_returns_dry_run_result() -> None:
    with _client() as client:
        result = execute_mutation(
            client,
            method="POST",
            path="/api/v2/zones",
            body={"domain": "example.com", "type": "master"},
            dry_run=True,
            summary="Would create zone example.com.",
        )
    assert isinstance(result, DryRunResult)
    assert result.request.method == "POST"
    assert result.request.url.endswith("/api/v2/zones")
    assert result.request.headers["Authorization"] == "Bearer tk"
    assert result.request.body == {"domain": "example.com", "type": "master"}


def test_dry_run_inlines_query_params_into_url() -> None:
    with _client() as client:
        result = execute_mutation(
            client,
            method="POST",
            path="/api/v2/zones",
            body={"domain": "example.com", "type": "master"},
            params={"test": 1},
            dry_run=True,
            summary="Would test-validate zone example.com.",
        )
    assert isinstance(result, DryRunResult)
    assert result.request.url.endswith("/api/v2/zones?test=1")


@respx.mock
def test_live_path_parses_json_dict() -> None:
    route = respx.post("https://my.rcodezero.at/api/v2/zones").mock(
        return_value=httpx.Response(201, json={"status": "ok", "id": 42}),
    )
    with _client() as client:
        result = execute_mutation(
            client,
            method="POST",
            path="/api/v2/zones",
            body={"domain": "example.com", "type": "master"},
            dry_run=False,
            summary="Would create zone example.com.",
        )
    assert route.called
    assert result == {"status": "ok", "id": 42}


@respx.mock
def test_live_path_wraps_bare_list() -> None:
    respx.put("https://my.rcodezero.at/api/v2/foo").mock(
        return_value=httpx.Response(200, json=[1, 2, 3]),
    )
    with _client() as client:
        result: Any = execute_mutation(
            client,
            method="PUT",
            path="/api/v2/foo",
            body={},
            dry_run=False,
            summary="fake",
        )
    assert result == {"data": [1, 2, 3]}


@respx.mock
def test_live_path_handles_204_no_content() -> None:
    respx.delete("https://my.rcodezero.at/api/v2/foo").mock(
        return_value=httpx.Response(204),
    )
    with _client() as client:
        result = execute_mutation(
            client,
            method="DELETE",
            path="/api/v2/foo",
            dry_run=False,
            summary="fake",
        )
    assert result == {"status": "ok"}
```

- [ ] **Step 1.2 — Run the test to verify it fails**

Run: `uv run pytest tests/unit/test_mutation_executor.py -v --no-cov`
Expected: FAIL with `ModuleNotFoundError: No module named 'rc0.client.mutations'`.

- [ ] **Step 1.3 — Implement the dispatcher**

```python
# src/rc0/client/mutations.py
"""Small dispatcher shared by every Phase-2 write command.

`execute_mutation` returns either a :class:`DryRunResult` (when dry-run is on)
or a parsed JSON response dict. Command modules stay short because of it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

from rc0.client.dry_run import build_dry_run

if TYPE_CHECKING:
    from rc0.client.dry_run import DryRunResult
    from rc0.client.http import Client


def execute_mutation(
    client: Client,
    *,
    method: str,
    path: str,
    body: Any = None,
    params: dict[str, Any] | None = None,
    dry_run: bool,
    summary: str,
    side_effects: list[str] | None = None,
) -> DryRunResult | dict[str, Any]:
    if dry_run:
        return build_dry_run(
            client,
            method=method,
            path=_with_query(path, params),
            body=body,
            summary=summary,
            side_effects=side_effects,
        )
    response = client.request(method, path, params=params, json=body)
    if response.status_code == 204 or not response.content:
        return {"status": "ok"}
    payload: Any = response.json()
    if isinstance(payload, dict):
        return payload
    return {"data": payload}


def _with_query(path: str, params: dict[str, Any] | None) -> str:
    if not params:
        return path
    return f"{path}?{urlencode(params, doseq=True)}"
```

- [ ] **Step 1.4 — Run the test to verify it passes**

Run: `uv run pytest tests/unit/test_mutation_executor.py -v --no-cov`
Expected: PASS (5 tests).

- [ ] **Step 1.5 — Commit**

```bash
git add src/rc0/client/mutations.py tests/unit/test_mutation_executor.py
git commit -m "feat(client): add execute_mutation dispatcher for Phase 2 writes"
```

---

## Task 2 — Confirmation prompt unit tests

**Files:**
- Test: `tests/unit/test_confirm.py`

`confirm.py` shipped in Phase 0 but had no coverage. Land coverage now so the
Phase 2 destructive commands can rely on it.

- [ ] **Step 2.1 — Write the failing tests**

```python
# tests/unit/test_confirm.py
"""Tests for interactive confirmation prompts."""

from __future__ import annotations

import io

import pytest

from rc0.client.errors import ConfirmationDeclined
from rc0.confirm import confirm_typed, confirm_yes_no


def test_confirm_typed_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("example.com\n"))
    err = io.StringIO()
    monkeypatch.setattr("sys.stderr", err)
    confirm_typed("example.com", summary="Would delete example.com.")
    assert "Would delete example.com." in err.getvalue()


def test_confirm_typed_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("other.test\n"))
    monkeypatch.setattr("sys.stderr", io.StringIO())
    with pytest.raises(ConfirmationDeclined):
        confirm_typed("example.com", summary="…")


def test_confirm_typed_empty_input_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    monkeypatch.setattr("sys.stderr", io.StringIO())
    with pytest.raises(ConfirmationDeclined):
        confirm_typed("example.com", summary="…")


def test_confirm_yes_no_accepts_y(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("y\n"))
    monkeypatch.setattr("sys.stderr", io.StringIO())
    confirm_yes_no("Proceed?")


def test_confirm_yes_no_accepts_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("yes\n"))
    monkeypatch.setattr("sys.stderr", io.StringIO())
    confirm_yes_no("Proceed?")


def test_confirm_yes_no_default_no(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("\n"))
    monkeypatch.setattr("sys.stderr", io.StringIO())
    with pytest.raises(ConfirmationDeclined):
        confirm_yes_no("Proceed?")


def test_confirm_yes_no_default_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("\n"))
    monkeypatch.setattr("sys.stderr", io.StringIO())
    confirm_yes_no("Proceed?", default_no=False)
```

- [ ] **Step 2.2 — Run the test to verify it passes**

Run: `uv run pytest tests/unit/test_confirm.py -v --no-cov`
Expected: PASS (7 tests). `confirm.py` already exists and behaves per the tests.

- [ ] **Step 2.3 — Commit**

```bash
git add tests/unit/test_confirm.py
git commit -m "test(confirm): cover confirm_typed / confirm_yes_no interactions"
```

---

## Task 3 — Zone write: request models + API wrappers

**Files:**
- Create: `src/rc0/models/zone_write.py`, `src/rc0/api/zones_write.py`
- Test: `tests/unit/test_zone_write_api.py`

- [ ] **Step 3.1 — Create the request models**

```python
# src/rc0/models/zone_write.py
"""Pydantic request bodies for POST/PUT/PATCH on /api/v2/zones[...]."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from rc0.models.common import Rc0Model

ZoneType = Literal["master", "slave"]


class CreateZoneRequest(Rc0Model):
    domain: str
    type: ZoneType
    masters: list[str] | None = None
    cds_cdnskey_publish: bool | None = None
    serial_auto_increment: bool | None = None


class UpdateZoneRequest(Rc0Model):
    type: ZoneType | None = None
    masters: list[str] | None = None
    cds_cdnskey_publish: bool | None = None
    serial_auto_increment: bool | None = None


class PatchZoneRequest(Rc0Model):
    zone_disabled: bool


class InboundXfrRequest(Rc0Model):
    tsigkey: str


class OutboundXfrRequest(Rc0Model):
    secondaries: list[str] = Field(default_factory=list)
    tsigkey: str = ""
```

- [ ] **Step 3.2 — Write the API wrapper tests**

```python
# tests/unit/test_zone_write_api.py
"""API wrapper tests for write operations against /api/v2/zones[...]."""

from __future__ import annotations

import httpx
import respx

from rc0.api import zones_write as api
from rc0.client.dry_run import DryRunResult
from rc0.client.http import Client


def _client() -> Client:
    return Client(api_url="https://my.rcodezero.at", token="tk")


@respx.mock
def test_create_zone_live() -> None:
    route = respx.post("https://my.rcodezero.at/api/v2/zones").mock(
        return_value=httpx.Response(201, json={"status": "ok", "domain": "example.com"}),
    )
    with _client() as client:
        result = api.create_zone(
            client,
            domain="example.com",
            zone_type="master",
            dry_run=False,
        )
    assert route.called
    assert route.calls.last.request.read() == b'{"domain":"example.com","type":"master"}'
    assert result == {"status": "ok", "domain": "example.com"}


def test_create_zone_dry_run_omits_null_fields() -> None:
    with _client() as client:
        result = api.create_zone(
            client,
            domain="example.com",
            zone_type="master",
            masters=None,
            dry_run=True,
        )
    assert isinstance(result, DryRunResult)
    assert result.request.body == {"domain": "example.com", "type": "master"}
    assert "example.com" in result.summary


def test_create_zone_dry_run_includes_masters() -> None:
    with _client() as client:
        result = api.create_zone(
            client,
            domain="example.com",
            zone_type="slave",
            masters=["10.0.0.1", "10.0.0.2"],
            dry_run=True,
        )
    assert isinstance(result, DryRunResult)
    assert result.request.body == {
        "domain": "example.com",
        "type": "slave",
        "masters": ["10.0.0.1", "10.0.0.2"],
    }


def test_patch_zone_disabled_dry_run() -> None:
    with _client() as client:
        result = api.patch_zone_disabled(
            client, zone="example.com", disabled=True, dry_run=True,
        )
    assert isinstance(result, DryRunResult)
    assert result.request.body == {"zone_disabled": True}
    assert "disable" in result.summary.lower()


def test_test_zone_dry_run_adds_test_query() -> None:
    with _client() as client:
        result = api.test_zone(
            client, domain="example.com", zone_type="master", dry_run=True,
        )
    assert isinstance(result, DryRunResult)
    assert result.request.url.endswith("/api/v2/zones?test=1")


@respx.mock
def test_delete_zone_live() -> None:
    respx.delete("https://my.rcodezero.at/api/v2/zones/example.com").mock(
        return_value=httpx.Response(204),
    )
    with _client() as client:
        result = api.delete_zone(client, zone="example.com", dry_run=False)
    assert result == {"status": "ok"}


@respx.mock
def test_retrieve_zone_live() -> None:
    respx.post("https://my.rcodezero.at/api/v2/zones/example.com/retrieve").mock(
        return_value=httpx.Response(200, json={"status": "ok"}),
    )
    with _client() as client:
        result = api.retrieve_zone(client, zone="example.com", dry_run=False)
    assert result == {"status": "ok"}


@respx.mock
def test_set_inbound_live_posts_tsigkey() -> None:
    route = respx.post("https://my.rcodezero.at/api/v2/zones/example.com/inbound").mock(
        return_value=httpx.Response(200, json={"tsigkey": "k"}),
    )
    with _client() as client:
        api.set_inbound(client, zone="example.com", tsigkey="k", dry_run=False)
    assert route.called
    assert route.calls.last.request.read() == b'{"tsigkey":"k"}'


@respx.mock
def test_unset_outbound_live_issues_delete() -> None:
    route = respx.delete("https://my.rcodezero.at/api/v2/zones/example.com/outbound").mock(
        return_value=httpx.Response(204),
    )
    with _client() as client:
        api.unset_outbound(client, zone="example.com", dry_run=False)
    assert route.called


def test_set_outbound_dry_run_serialises_secondaries_and_tsigkey() -> None:
    with _client() as client:
        result = api.set_outbound(
            client,
            zone="example.com",
            secondaries=["10.0.0.1"],
            tsigkey="k",
            dry_run=True,
        )
    assert isinstance(result, DryRunResult)
    assert result.request.body == {"secondaries": ["10.0.0.1"], "tsigkey": "k"}
```

- [ ] **Step 3.3 — Run the test to verify it fails**

Run: `uv run pytest tests/unit/test_zone_write_api.py -v --no-cov`
Expected: FAIL with `ModuleNotFoundError: No module named 'rc0.api.zones_write'`.

- [ ] **Step 3.4 — Implement the API wrappers**

```python
# src/rc0/api/zones_write.py
"""Write-endpoint wrappers for /api/v2/zones[...]."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rc0.client.mutations import execute_mutation
from rc0.models.zone_write import (
    CreateZoneRequest,
    InboundXfrRequest,
    OutboundXfrRequest,
    PatchZoneRequest,
    UpdateZoneRequest,
    ZoneType,
)

if TYPE_CHECKING:
    from rc0.client.dry_run import DryRunResult
    from rc0.client.http import Client


def _body(model: Any) -> dict[str, Any]:
    return model.model_dump(exclude_none=True)


def create_zone(
    client: Client,
    *,
    domain: str,
    zone_type: ZoneType,
    masters: list[str] | None = None,
    cds_cdnskey_publish: bool | None = None,
    serial_auto_increment: bool | None = None,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    body = _body(
        CreateZoneRequest(
            domain=domain,
            type=zone_type,
            masters=masters,
            cds_cdnskey_publish=cds_cdnskey_publish,
            serial_auto_increment=serial_auto_increment,
        ),
    )
    master_note = f" with {len(masters)} master IP(s)" if masters else ""
    return execute_mutation(
        client,
        method="POST",
        path="/api/v2/zones",
        body=body,
        dry_run=dry_run,
        summary=f"Would create {zone_type} zone {domain}{master_note}.",
        side_effects=["creates_zone"],
    )


def update_zone(
    client: Client,
    *,
    zone: str,
    zone_type: ZoneType | None = None,
    masters: list[str] | None = None,
    cds_cdnskey_publish: bool | None = None,
    serial_auto_increment: bool | None = None,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    body = _body(
        UpdateZoneRequest(
            type=zone_type,
            masters=masters,
            cds_cdnskey_publish=cds_cdnskey_publish,
            serial_auto_increment=serial_auto_increment,
        ),
    )
    return execute_mutation(
        client,
        method="PUT",
        path=f"/api/v2/zones/{zone}",
        body=body,
        dry_run=dry_run,
        summary=f"Would update zone {zone}.",
    )


def patch_zone_disabled(
    client: Client,
    *,
    zone: str,
    disabled: bool,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    body = _body(PatchZoneRequest(zone_disabled=disabled))
    verb = "disable" if disabled else "enable"
    return execute_mutation(
        client,
        method="PATCH",
        path=f"/api/v2/zones/{zone}",
        body=body,
        dry_run=dry_run,
        summary=f"Would {verb} zone {zone}.",
    )


def delete_zone(
    client: Client,
    *,
    zone: str,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    return execute_mutation(
        client,
        method="DELETE",
        path=f"/api/v2/zones/{zone}",
        dry_run=dry_run,
        summary=f"Would delete zone {zone}.",
        side_effects=["deletes_zone", "discards_rrsets"],
    )


def retrieve_zone(
    client: Client,
    *,
    zone: str,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    return execute_mutation(
        client,
        method="POST",
        path=f"/api/v2/zones/{zone}/retrieve",
        dry_run=dry_run,
        summary=f"Would queue a zone transfer for {zone}.",
    )


def test_zone(
    client: Client,
    *,
    domain: str,
    zone_type: ZoneType,
    masters: list[str] | None = None,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    """POST /api/v2/zones?test=1 — the API's own validation call."""
    body = _body(
        CreateZoneRequest(domain=domain, type=zone_type, masters=masters),
    )
    return execute_mutation(
        client,
        method="POST",
        path="/api/v2/zones",
        body=body,
        params={"test": 1},
        dry_run=dry_run,
        summary=f"Would ask the API to validate {domain} ({zone_type}).",
    )


def set_inbound(
    client: Client,
    *,
    zone: str,
    tsigkey: str,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    body = _body(InboundXfrRequest(tsigkey=tsigkey))
    return execute_mutation(
        client,
        method="POST",
        path=f"/api/v2/zones/{zone}/inbound",
        body=body,
        dry_run=dry_run,
        summary=f"Would set inbound TSIG key for {zone} to {tsigkey!r}.",
    )


def unset_inbound(
    client: Client,
    *,
    zone: str,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    return execute_mutation(
        client,
        method="DELETE",
        path=f"/api/v2/zones/{zone}/inbound",
        dry_run=dry_run,
        summary=f"Would clear inbound TSIG key for {zone}.",
    )


def show_inbound(client: Client, *, zone: str) -> dict[str, Any]:
    response = client.get(f"/api/v2/zones/{zone}/inbound")
    payload: Any = response.json()
    return payload if isinstance(payload, dict) else {"data": payload}


def set_outbound(
    client: Client,
    *,
    zone: str,
    secondaries: list[str] | None,
    tsigkey: str | None,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    body = _body(
        OutboundXfrRequest(
            secondaries=secondaries or [],
            tsigkey=tsigkey or "",
        ),
    )
    return execute_mutation(
        client,
        method="POST",
        path=f"/api/v2/zones/{zone}/outbound",
        body=body,
        dry_run=dry_run,
        summary=f"Would set outbound xfr for {zone}.",
    )


def unset_outbound(
    client: Client,
    *,
    zone: str,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    return execute_mutation(
        client,
        method="DELETE",
        path=f"/api/v2/zones/{zone}/outbound",
        dry_run=dry_run,
        summary=f"Would clear outbound xfr config for {zone}.",
    )


def show_outbound(client: Client, *, zone: str) -> dict[str, Any]:
    response = client.get(f"/api/v2/zones/{zone}/outbound")
    payload: Any = response.json()
    return payload if isinstance(payload, dict) else {"data": payload}
```

- [ ] **Step 3.5 — Run the test to verify it passes**

Run: `uv run pytest tests/unit/test_zone_write_api.py -v --no-cov`
Expected: PASS (10 tests).

- [ ] **Step 3.6 — Commit**

```bash
git add src/rc0/models/zone_write.py src/rc0/api/zones_write.py tests/unit/test_zone_write_api.py
git commit -m "feat(api): zone write endpoints with dry-run support"
```

---

## Task 4 — Zone write: CLI commands

**Files:**
- Modify: `src/rc0/commands/zone.py`
- Create: `tests/integration/test_zone_write_commands.py`

- [ ] **Step 4.1 — Write the integration tests**

```python
# tests/integration/test_zone_write_commands.py
"""Zone write-command integration tests."""

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
def test_zone_create_live(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.post("https://my.rcodezero.at/api/v2/zones").mock(
        return_value=httpx.Response(201, json={"status": "ok", "domain": "example.com"}),
    )
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json", "zone", "create", "example.com", "--type", "master"],
    )
    assert r.exit_code == 0, r.stdout
    assert route.called
    assert route.calls.last.request.read() == b'{"domain":"example.com","type":"master"}'
    assert json.loads(r.stdout)["status"] == "ok"


def test_zone_create_dry_run(cli: CliRunner, isolated_config: Path) -> None:
    r = cli.invoke(
        app,
        [
            "--token", "tk", "-o", "json", "--dry-run",
            "zone", "create", "example.com",
            "--type", "master", "--master", "10.0.0.1",
        ],
    )
    assert r.exit_code == 0, r.stdout
    parsed = json.loads(r.stdout)
    assert parsed["dry_run"] is True
    assert parsed["request"]["method"] == "POST"
    assert parsed["request"]["url"].endswith("/api/v2/zones")
    assert parsed["request"]["headers"]["Authorization"] == "Bearer ***REDACTED***"
    assert parsed["request"]["body"] == {
        "domain": "example.com", "type": "master", "masters": ["10.0.0.1"],
    }
    assert "create" in parsed["summary"].lower()


@respx.mock
def test_zone_update_live(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.put("https://my.rcodezero.at/api/v2/zones/example.com").mock(
        return_value=httpx.Response(200, json={"status": "ok"}),
    )
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json",
         "zone", "update", "example.com",
         "--master", "10.0.0.1", "--master", "10.0.0.2"],
    )
    assert r.exit_code == 0, r.stdout
    assert route.called
    assert route.calls.last.request.read() == b'{"masters":["10.0.0.1","10.0.0.2"]}'


@respx.mock
def test_zone_enable_live(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.patch("https://my.rcodezero.at/api/v2/zones/example.com").mock(
        return_value=httpx.Response(200, json={"status": "ok"}),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "zone", "enable", "example.com"])
    assert r.exit_code == 0, r.stdout
    assert route.calls.last.request.read() == b'{"zone_disabled":false}'


@respx.mock
def test_zone_disable_live(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.patch("https://my.rcodezero.at/api/v2/zones/example.com").mock(
        return_value=httpx.Response(200, json={"status": "ok"}),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "zone", "disable", "example.com"])
    assert r.exit_code == 0, r.stdout
    assert route.calls.last.request.read() == b'{"zone_disabled":true}'


@respx.mock
def test_zone_delete_requires_typed_confirmation(
    cli: CliRunner, isolated_config: Path,
) -> None:
    # Declining — wrong typed answer → exit 12, DELETE never sent.
    route = respx.delete("https://my.rcodezero.at/api/v2/zones/example.com").mock(
        return_value=httpx.Response(204),
    )
    r = cli.invoke(
        app,
        ["--token", "tk", "zone", "delete", "example.com"],
        input="nope\n",
    )
    assert r.exit_code == 12, r.stdout
    assert not route.called


@respx.mock
def test_zone_delete_typed_ok_proceeds(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.delete("https://my.rcodezero.at/api/v2/zones/example.com").mock(
        return_value=httpx.Response(204),
    )
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json", "zone", "delete", "example.com"],
        input="example.com\n",
    )
    assert r.exit_code == 0, r.stdout
    assert route.called


@respx.mock
def test_zone_delete_yes_skips_prompt(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.delete("https://my.rcodezero.at/api/v2/zones/example.com").mock(
        return_value=httpx.Response(204),
    )
    r = cli.invoke(
        app,
        ["--token", "tk", "-y", "-o", "json", "zone", "delete", "example.com"],
    )
    assert r.exit_code == 0, r.stdout
    assert route.called


def test_zone_delete_dry_run_skips_prompt_and_network(
    cli: CliRunner, isolated_config: Path,
) -> None:
    # No respx route registered; if the command reached the network, respx would 500.
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json", "--dry-run", "zone", "delete", "example.com"],
    )
    assert r.exit_code == 0, r.stdout
    parsed = json.loads(r.stdout)
    assert parsed["dry_run"] is True
    assert parsed["request"]["method"] == "DELETE"


@respx.mock
def test_zone_retrieve_live(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.post("https://my.rcodezero.at/api/v2/zones/example.com/retrieve").mock(
        return_value=httpx.Response(200, json={"status": "ok"}),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "zone", "retrieve", "example.com"])
    assert r.exit_code == 0, r.stdout
    assert route.called


@respx.mock
def test_zone_test_appends_query_param(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.post(
        "https://my.rcodezero.at/api/v2/zones",
        params={"test": 1},
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json", "zone", "test", "example.com", "--type", "master"],
    )
    assert r.exit_code == 0, r.stdout
    assert route.called


@respx.mock
def test_zone_xfr_in_show(cli: CliRunner, isolated_config: Path) -> None:
    respx.get("https://my.rcodezero.at/api/v2/zones/example.com/inbound").mock(
        return_value=httpx.Response(200, json={"tsigkey": "k"}),
    )
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json", "zone", "xfr-in", "show", "example.com"],
    )
    assert r.exit_code == 0, r.stdout
    assert json.loads(r.stdout)["tsigkey"] == "k"


@respx.mock
def test_zone_xfr_in_set(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.post("https://my.rcodezero.at/api/v2/zones/example.com/inbound").mock(
        return_value=httpx.Response(200, json={"tsigkey": "k"}),
    )
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json",
         "zone", "xfr-in", "set", "example.com", "--tsigkey", "k"],
    )
    assert r.exit_code == 0, r.stdout
    assert route.called
    assert route.calls.last.request.read() == b'{"tsigkey":"k"}'


@respx.mock
def test_zone_xfr_in_unset(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.delete("https://my.rcodezero.at/api/v2/zones/example.com/inbound").mock(
        return_value=httpx.Response(204),
    )
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json", "zone", "xfr-in", "unset", "example.com"],
    )
    assert r.exit_code == 0, r.stdout
    assert route.called


@respx.mock
def test_zone_xfr_out_set_empty_secondaries_ok(
    cli: CliRunner, isolated_config: Path,
) -> None:
    # The API accepts an empty secondaries array (it means "clear them") — make
    # sure our default serialises as []; not null.
    route = respx.post("https://my.rcodezero.at/api/v2/zones/example.com/outbound").mock(
        return_value=httpx.Response(200, json={"secondaries": [], "tsigkey": "k"}),
    )
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json",
         "zone", "xfr-out", "set", "example.com", "--tsigkey", "k"],
    )
    assert r.exit_code == 0, r.stdout
    assert route.called
    assert route.calls.last.request.read() == b'{"secondaries":[],"tsigkey":"k"}'
```

- [ ] **Step 4.2 — Run the tests to verify they fail**

Run: `uv run pytest tests/integration/test_zone_write_commands.py -v --no-cov`
Expected: FAIL — the commands don't exist yet. Errors like `Usage: rc0 zone [OPTIONS] COMMAND [ARGS]... Try 'rc0 zone --help' for help. Error: No such command 'create'.`

- [ ] **Step 4.3 — Extend `commands/zone.py` with the new subcommands**

Append (do not replace) to `src/rc0/commands/zone.py`. Add these imports at the top near existing ones:

```python
from enum import StrEnum

from rc0.api import zones_write as zones_write_api
from rc0.client.dry_run import DryRunResult
from rc0.confirm import confirm_typed
```

Add the subcommands at the bottom of the file:

```python
# ---------------------------------------------------------- Phase 2 mutations


class ZoneTypeChoice(StrEnum):
    """Typer-friendly enum. Values match the API's lowercase `type2` enum."""

    master = "master"
    slave = "slave"


TypeOpt = Annotated[
    ZoneTypeChoice,
    typer.Option(
        "--type",
        help="Zone type: master or slave.",
        case_sensitive=False,
    ),
]
MasterOpt = Annotated[
    list[str] | None,
    typer.Option(
        "--master",
        help="Primary nameserver IP. Repeat for multiple; required for slave zones.",
    ),
]
CdsOpt = Annotated[
    bool | None,
    typer.Option(
        "--cds/--no-cds",
        help="Publish CDS/CDNSKEY records (RFC 7344).",
    ),
]
SerialAutoOpt = Annotated[
    bool | None,
    typer.Option(
        "--serial-auto/--no-serial-auto",
        help="Auto-increment serial on RRset updates (master zones only).",
    ),
]
TsigKeyOpt = Annotated[
    str,
    typer.Option("--tsigkey", help="Name of a preconfigured TSIG key."),
]


def _render_mutation(result: DryRunResult | dict[str, object], state: AppState) -> None:
    payload = (
        result.to_dict() if isinstance(result, DryRunResult) else result
    )
    typer.echo(render(payload, fmt=state.effective_output))


@app.command("create")
def create_cmd(
    ctx: typer.Context,
    domain: Annotated[str, typer.Argument(help="Domain to add.")],
    zone_type: TypeOpt = ZoneTypeChoice.master,
    masters: MasterOpt = None,
    cds: CdsOpt = None,
    serial_auto: SerialAutoOpt = None,
) -> None:
    """Add a new zone. API: POST /api/v2/zones"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = zones_write_api.create_zone(
            client,
            domain=domain,
            zone_type=zone_type.value,  # type: ignore[arg-type]
            masters=masters,
            cds_cdnskey_publish=cds,
            serial_auto_increment=serial_auto,
            dry_run=state.dry_run,
        )
    _render_mutation(result, state)


@app.command("update")
def update_cmd(
    ctx: typer.Context,
    zone: ZoneArg,
    zone_type: Annotated[
        ZoneTypeChoice | None,
        typer.Option("--type", help="Change zone type.", case_sensitive=False),
    ] = None,
    masters: MasterOpt = None,
    cds: CdsOpt = None,
    serial_auto: SerialAutoOpt = None,
) -> None:
    """Update an existing zone. API: PUT /api/v2/zones/{zone}"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = zones_write_api.update_zone(
            client,
            zone=zone,
            zone_type=zone_type.value if zone_type else None,  # type: ignore[arg-type]
            masters=masters,
            cds_cdnskey_publish=cds,
            serial_auto_increment=serial_auto,
            dry_run=state.dry_run,
        )
    _render_mutation(result, state)


@app.command("enable")
def enable_cmd(ctx: typer.Context, zone: ZoneArg) -> None:
    """Re-enable a disabled zone. API: PATCH /api/v2/zones/{zone}"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = zones_write_api.patch_zone_disabled(
            client, zone=zone, disabled=False, dry_run=state.dry_run,
        )
    _render_mutation(result, state)


@app.command("disable")
def disable_cmd(ctx: typer.Context, zone: ZoneArg) -> None:
    """Disable a zone without deleting it. API: PATCH /api/v2/zones/{zone}"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = zones_write_api.patch_zone_disabled(
            client, zone=zone, disabled=True, dry_run=state.dry_run,
        )
    _render_mutation(result, state)


@app.command("delete")
def delete_cmd(ctx: typer.Context, zone: ZoneArg) -> None:
    """Delete a zone. API: DELETE /api/v2/zones/{zone}"""
    state: AppState = ctx.obj
    if not state.dry_run and not state.yes:
        confirm_typed(
            zone,
            summary=f"Would delete zone {zone} and discard every RRset. This cannot be undone.",
        )
    with _client(state) as client:
        result = zones_write_api.delete_zone(
            client, zone=zone, dry_run=state.dry_run,
        )
    _render_mutation(result, state)


@app.command("retrieve")
def retrieve_cmd(ctx: typer.Context, zone: ZoneArg) -> None:
    """Queue an immediate zone transfer. API: POST /api/v2/zones/{zone}/retrieve"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = zones_write_api.retrieve_zone(
            client, zone=zone, dry_run=state.dry_run,
        )
    _render_mutation(result, state)


@app.command("test")
def test_cmd(
    ctx: typer.Context,
    domain: Annotated[str, typer.Argument(help="Domain to validate.")],
    zone_type: TypeOpt = ZoneTypeChoice.master,
    masters: MasterOpt = None,
) -> None:
    """Server-side validation (does NOT create). API: POST /api/v2/zones?test=1

    This is distinct from --dry-run: the API runs its own checks against the
    would-be zone. Use --dry-run on top to show what this command would send
    without contacting the API at all.
    """
    state: AppState = ctx.obj
    with _client(state) as client:
        result = zones_write_api.test_zone(
            client,
            domain=domain,
            zone_type=zone_type.value,  # type: ignore[arg-type]
            masters=masters,
            dry_run=state.dry_run,
        )
    _render_mutation(result, state)


# -------------------------------------------------------- xfr-in / xfr-out subgroups

xfr_in = typer.Typer(name="xfr-in", help="Per-zone inbound transfer config.", no_args_is_help=True)
xfr_out = typer.Typer(name="xfr-out", help="Per-zone outbound transfer config.", no_args_is_help=True)
app.add_typer(xfr_in, name="xfr-in")
app.add_typer(xfr_out, name="xfr-out")


@xfr_in.command("show")
def xfr_in_show(ctx: typer.Context, zone: ZoneArg) -> None:
    """Show the zone's inbound TSIG config. API: GET /api/v2/zones/{zone}/inbound"""
    state: AppState = ctx.obj
    with _client(state) as client:
        payload = zones_write_api.show_inbound(client, zone=zone)
    typer.echo(render(payload, fmt=state.effective_output))


@xfr_in.command("set")
def xfr_in_set(
    ctx: typer.Context,
    zone: ZoneArg,
    tsigkey: TsigKeyOpt,
) -> None:
    """Set the inbound TSIG key. API: POST /api/v2/zones/{zone}/inbound"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = zones_write_api.set_inbound(
            client, zone=zone, tsigkey=tsigkey, dry_run=state.dry_run,
        )
    _render_mutation(result, state)


@xfr_in.command("unset")
def xfr_in_unset(ctx: typer.Context, zone: ZoneArg) -> None:
    """Clear the inbound TSIG key. API: DELETE /api/v2/zones/{zone}/inbound"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = zones_write_api.unset_inbound(
            client, zone=zone, dry_run=state.dry_run,
        )
    _render_mutation(result, state)


@xfr_out.command("show")
def xfr_out_show(ctx: typer.Context, zone: ZoneArg) -> None:
    """Show the zone's outbound xfr config. API: GET /api/v2/zones/{zone}/outbound"""
    state: AppState = ctx.obj
    with _client(state) as client:
        payload = zones_write_api.show_outbound(client, zone=zone)
    typer.echo(render(payload, fmt=state.effective_output))


@xfr_out.command("set")
def xfr_out_set(
    ctx: typer.Context,
    zone: ZoneArg,
    secondaries: Annotated[
        list[str] | None,
        typer.Option(
            "--secondary",
            help="IP of a secondary nameserver. Repeat for multiple; empty = clear.",
        ),
    ] = None,
    tsigkey: Annotated[
        str | None,
        typer.Option("--tsigkey", help="Preconfigured TSIG key; omit to clear."),
    ] = None,
) -> None:
    """Set outbound xfr. API: POST /api/v2/zones/{zone}/outbound"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = zones_write_api.set_outbound(
            client,
            zone=zone,
            secondaries=secondaries,
            tsigkey=tsigkey,
            dry_run=state.dry_run,
        )
    _render_mutation(result, state)


@xfr_out.command("unset")
def xfr_out_unset(ctx: typer.Context, zone: ZoneArg) -> None:
    """Clear outbound xfr. API: DELETE /api/v2/zones/{zone}/outbound"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = zones_write_api.unset_outbound(
            client, zone=zone, dry_run=state.dry_run,
        )
    _render_mutation(result, state)
```

- [ ] **Step 4.4 — Run the tests to verify they pass**

Run: `uv run pytest tests/integration/test_zone_write_commands.py -v --no-cov`
Expected: PASS (14 tests).

- [ ] **Step 4.5 — Sanity-check the Typer help surface**

Run:
```
uv run rc0 zone --help
uv run rc0 zone xfr-in --help
uv run rc0 zone xfr-out --help
```
Expected: all three exit 0 and list the new commands.

- [ ] **Step 4.6 — Commit**

```bash
git add src/rc0/commands/zone.py tests/integration/test_zone_write_commands.py
git commit -m "feat(cli): zone create/update/enable/disable/delete/retrieve/test + xfr-in/xfr-out"
```

---

## Task 5 — TSIG write: models, API wrappers, CLI

**Files:**
- Create: `src/rc0/models/tsig_write.py`, `src/rc0/api/tsig_write.py`
- Modify: `src/rc0/commands/tsig.py`
- Test: `tests/integration/test_tsig_write_commands.py`

- [ ] **Step 5.1 — Add the request models**

```python
# src/rc0/models/tsig_write.py
"""Pydantic request bodies for POST/PUT on /api/v2/tsig[...]."""

from __future__ import annotations

from typing import Literal

from rc0.models.common import Rc0Model

TSIG_ALGORITHMS: tuple[str, ...] = (
    "hmac-md5",
    "hmac-sha1",
    "hmac-sha224",
    "hmac-sha256",
    "hmac-sha384",
    "hmac-sha512",
)

Algorithm = Literal[
    "hmac-md5",
    "hmac-sha1",
    "hmac-sha224",
    "hmac-sha256",
    "hmac-sha384",
    "hmac-sha512",
]


class AddTsigRequest(Rc0Model):
    name: str
    algorithm: Algorithm
    secret: str


class UpdateTsigRequest(Rc0Model):
    algorithm: Algorithm
    secret: str
```

- [ ] **Step 5.2 — Add the API wrappers**

```python
# src/rc0/api/tsig_write.py
"""TSIG write-endpoint wrappers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rc0.client.mutations import execute_mutation
from rc0.models.tsig_write import AddTsigRequest, Algorithm, UpdateTsigRequest

if TYPE_CHECKING:
    from rc0.client.dry_run import DryRunResult
    from rc0.client.http import Client


def add_tsig(
    client: Client,
    *,
    name: str,
    algorithm: Algorithm,
    secret: str,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    body = AddTsigRequest(
        name=name, algorithm=algorithm, secret=secret,
    ).model_dump()
    return execute_mutation(
        client,
        method="POST",
        path="/api/v2/tsig",
        body=body,
        dry_run=dry_run,
        summary=f"Would add TSIG key {name} ({algorithm}).",
    )


def update_tsig(
    client: Client,
    *,
    name: str,
    algorithm: Algorithm,
    secret: str,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    body = UpdateTsigRequest(algorithm=algorithm, secret=secret).model_dump()
    return execute_mutation(
        client,
        method="PUT",
        path=f"/api/v2/tsig/{name}",
        body=body,
        dry_run=dry_run,
        summary=f"Would update TSIG key {name} ({algorithm}).",
    )


def delete_tsig(
    client: Client, *, name: str, dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    return execute_mutation(
        client,
        method="DELETE",
        path=f"/api/v2/tsig/{name}",
        dry_run=dry_run,
        summary=f"Would delete TSIG key {name}.",
    )
```

- [ ] **Step 5.3 — Write the CLI integration tests**

```python
# tests/integration/test_tsig_write_commands.py
"""TSIG write-command integration tests."""

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
def test_tsig_add_live(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.post("https://my.rcodezero.at/api/v2/tsig").mock(
        return_value=httpx.Response(
            201,
            json={"id": 1, "name": "k1", "algorithm": "hmac-sha256", "secret": "abc"},
        ),
    )
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json",
         "tsig", "add", "k1",
         "--algorithm", "hmac-sha256", "--secret", "abc"],
    )
    assert r.exit_code == 0, r.stdout
    assert route.called
    assert route.calls.last.request.read() == (
        b'{"name":"k1","algorithm":"hmac-sha256","secret":"abc"}'
    )


def test_tsig_add_rejects_bad_algorithm(cli: CliRunner, isolated_config: Path) -> None:
    r = cli.invoke(
        app,
        ["--token", "tk",
         "tsig", "add", "k1",
         "--algorithm", "hmac-sha-BROKEN", "--secret", "abc"],
    )
    assert r.exit_code == 2, r.stdout  # Typer usage error


def test_tsig_add_dry_run(cli: CliRunner, isolated_config: Path) -> None:
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json", "--dry-run",
         "tsig", "add", "k1",
         "--algorithm", "hmac-sha256", "--secret", "abc"],
    )
    assert r.exit_code == 0, r.stdout
    parsed = json.loads(r.stdout)
    assert parsed["dry_run"] is True
    assert parsed["request"]["body"] == {
        "name": "k1", "algorithm": "hmac-sha256", "secret": "abc",
    }


@respx.mock
def test_tsig_update_live(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.put("https://my.rcodezero.at/api/v2/tsig/k1").mock(
        return_value=httpx.Response(200, json={"status": "ok"}),
    )
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json",
         "tsig", "update", "k1",
         "--algorithm", "hmac-sha512", "--secret", "xyz"],
    )
    assert r.exit_code == 0, r.stdout
    assert route.called
    assert route.calls.last.request.read() == b'{"algorithm":"hmac-sha512","secret":"xyz"}'


@respx.mock
def test_tsig_delete_requires_yesno(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.delete("https://my.rcodezero.at/api/v2/tsig/k1").mock(
        return_value=httpx.Response(204),
    )
    r = cli.invoke(
        app,
        ["--token", "tk", "tsig", "delete", "k1"],
        input="\n",  # default-no
    )
    assert r.exit_code == 12, r.stdout
    assert not route.called


@respx.mock
def test_tsig_delete_y_proceeds(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.delete("https://my.rcodezero.at/api/v2/tsig/k1").mock(
        return_value=httpx.Response(204),
    )
    r = cli.invoke(
        app,
        ["--token", "tk", "tsig", "delete", "k1"],
        input="y\n",
    )
    assert r.exit_code == 0, r.stdout
    assert route.called


@respx.mock
def test_tsig_delete_yes_flag_skips_prompt(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.delete("https://my.rcodezero.at/api/v2/tsig/k1").mock(
        return_value=httpx.Response(204),
    )
    r = cli.invoke(app, ["--token", "tk", "-y", "tsig", "delete", "k1"])
    assert r.exit_code == 0, r.stdout
    assert route.called
```

- [ ] **Step 5.4 — Run the tests to verify they fail**

Run: `uv run pytest tests/integration/test_tsig_write_commands.py -v --no-cov`
Expected: FAIL — no commands yet.

- [ ] **Step 5.5 — Extend `commands/tsig.py`**

Append to `src/rc0/commands/tsig.py`. Add imports alongside existing ones:

```python
from enum import StrEnum

from rc0.api import tsig_write as tsig_write_api
from rc0.client.dry_run import DryRunResult
from rc0.confirm import confirm_yes_no
```

Add subcommands at end of file:

```python
class AlgorithmChoice(StrEnum):
    """Typer-friendly enum of the RcodeZero-supported TSIG algorithms."""

    hmac_md5 = "hmac-md5"
    hmac_sha1 = "hmac-sha1"
    hmac_sha224 = "hmac-sha224"
    hmac_sha256 = "hmac-sha256"
    hmac_sha384 = "hmac-sha384"
    hmac_sha512 = "hmac-sha512"


AlgorithmOpt = Annotated[
    AlgorithmChoice,
    typer.Option("--algorithm", help="TSIG algorithm.", case_sensitive=False),
]
SecretOpt = Annotated[
    str,
    typer.Option("--secret", help="Base64-encoded shared secret."),
]


def _render_mutation(result: DryRunResult | dict[str, object], state: AppState) -> None:
    payload = result.to_dict() if isinstance(result, DryRunResult) else result
    typer.echo(render(payload, fmt=state.effective_output))


@app.command("add")
def add_cmd(
    ctx: typer.Context,
    name: NameArg,
    algorithm: AlgorithmOpt,
    secret: SecretOpt,
) -> None:
    """Add a TSIG key. API: POST /api/v2/tsig"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = tsig_write_api.add_tsig(
            client,
            name=name,
            algorithm=algorithm.value,  # type: ignore[arg-type]
            secret=secret,
            dry_run=state.dry_run,
        )
    _render_mutation(result, state)


@app.command("update")
def update_cmd(
    ctx: typer.Context,
    name: NameArg,
    algorithm: AlgorithmOpt,
    secret: SecretOpt,
) -> None:
    """Update a TSIG key. API: PUT /api/v2/tsig/{keyname}"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = tsig_write_api.update_tsig(
            client,
            name=name,
            algorithm=algorithm.value,  # type: ignore[arg-type]
            secret=secret,
            dry_run=state.dry_run,
        )
    _render_mutation(result, state)


@app.command("delete")
def delete_cmd(ctx: typer.Context, name: NameArg) -> None:
    """Delete a TSIG key. API: DELETE /api/v2/tsig/{keyname}"""
    state: AppState = ctx.obj
    if not state.dry_run and not state.yes:
        confirm_yes_no(f"Would delete TSIG key {name}.")
    with _client(state) as client:
        result = tsig_write_api.delete_tsig(client, name=name, dry_run=state.dry_run)
    _render_mutation(result, state)
```

- [ ] **Step 5.6 — Run the tests to verify they pass**

Run: `uv run pytest tests/integration/test_tsig_write_commands.py -v --no-cov`
Expected: PASS (7 tests).

- [ ] **Step 5.7 — Commit**

```bash
git add src/rc0/models/tsig_write.py src/rc0/api/tsig_write.py \
        src/rc0/commands/tsig.py tests/integration/test_tsig_write_commands.py
git commit -m "feat(cli): tsig add/update/delete"
```

---

## Task 6 — Settings write: API wrappers + CLI

**Files:**
- Create: `src/rc0/api/settings_write.py`
- Modify: `src/rc0/commands/settings.py`
- Test: `tests/integration/test_settings_write_commands.py`

- [ ] **Step 6.1 — Add the API wrappers**

```python
# src/rc0/api/settings_write.py
"""Write-endpoint wrappers for /api/v2/settings[...]."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rc0.client.mutations import execute_mutation

if TYPE_CHECKING:
    from rc0.client.dry_run import DryRunResult
    from rc0.client.http import Client


def set_secondaries(
    client: Client, *, ips: list[str], dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    return execute_mutation(
        client,
        method="PUT",
        path="/api/v2/settings/secondaries",
        body={"secondaries": ips},
        dry_run=dry_run,
        summary=f"Would set {len(ips)} account-wide secondary(ies).",
    )


def unset_secondaries(
    client: Client, *, dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    return execute_mutation(
        client,
        method="DELETE",
        path="/api/v2/settings/secondaries",
        dry_run=dry_run,
        summary="Would clear account-wide secondaries.",
    )


def set_tsig_in(
    client: Client, *, tsigkey: str, dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    return execute_mutation(
        client,
        method="PUT",
        path="/api/v2/settings/tsig/in",
        body={"tsigkey": tsigkey},
        dry_run=dry_run,
        summary=f"Would set account-wide inbound TSIG key to {tsigkey!r}.",
    )


def unset_tsig_in(
    client: Client, *, dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    return execute_mutation(
        client,
        method="DELETE",
        path="/api/v2/settings/tsig/in",
        dry_run=dry_run,
        summary="Would clear account-wide inbound TSIG key.",
    )


def set_tsig_out(
    client: Client, *, tsigkey: str, dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    return execute_mutation(
        client,
        method="PUT",
        path="/api/v2/settings/tsig/out",
        body={"tsigkey": tsigkey},
        dry_run=dry_run,
        summary=f"Would set account-wide outbound TSIG key to {tsigkey!r}.",
    )


def unset_tsig_out(
    client: Client, *, dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    return execute_mutation(
        client,
        method="DELETE",
        path="/api/v2/settings/tsig/out",
        dry_run=dry_run,
        summary="Would clear account-wide outbound TSIG key.",
    )
```

- [ ] **Step 6.2 — Write the CLI tests**

```python
# tests/integration/test_settings_write_commands.py
"""Settings write-command integration tests."""

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
def test_secondaries_set_live(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.put("https://my.rcodezero.at/api/v2/settings/secondaries").mock(
        return_value=httpx.Response(200, json={"status": "ok"}),
    )
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json",
         "settings", "secondaries", "set",
         "--ip", "10.0.0.1", "--ip", "10.0.0.2"],
    )
    assert r.exit_code == 0, r.stdout
    assert route.called
    assert route.calls.last.request.read() == b'{"secondaries":["10.0.0.1","10.0.0.2"]}'


def test_secondaries_set_requires_ip(cli: CliRunner, isolated_config: Path) -> None:
    r = cli.invoke(
        app,
        ["--token", "tk", "settings", "secondaries", "set"],
    )
    assert r.exit_code == 2, r.stdout  # Typer usage error


@respx.mock
def test_secondaries_unset_live(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.delete("https://my.rcodezero.at/api/v2/settings/secondaries").mock(
        return_value=httpx.Response(204),
    )
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json", "settings", "secondaries", "unset"],
    )
    assert r.exit_code == 0, r.stdout
    assert route.called


def test_secondaries_set_dry_run(cli: CliRunner, isolated_config: Path) -> None:
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json", "--dry-run",
         "settings", "secondaries", "set", "--ip", "10.0.0.1"],
    )
    assert r.exit_code == 0, r.stdout
    parsed = json.loads(r.stdout)
    assert parsed["dry_run"] is True
    assert parsed["request"]["method"] == "PUT"
    assert parsed["request"]["body"] == {"secondaries": ["10.0.0.1"]}


@respx.mock
def test_tsig_in_set_live(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.put("https://my.rcodezero.at/api/v2/settings/tsig/in").mock(
        return_value=httpx.Response(200, json={"status": "ok"}),
    )
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json",
         "settings", "tsig-in", "set", "k1"],
    )
    assert r.exit_code == 0, r.stdout
    assert route.called
    assert route.calls.last.request.read() == b'{"tsigkey":"k1"}'


@respx.mock
def test_tsig_in_unset_live(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.delete("https://my.rcodezero.at/api/v2/settings/tsig/in").mock(
        return_value=httpx.Response(204),
    )
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json", "settings", "tsig-in", "unset"],
    )
    assert r.exit_code == 0, r.stdout
    assert route.called


@respx.mock
def test_tsig_out_set_live(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.put("https://my.rcodezero.at/api/v2/settings/tsig/out").mock(
        return_value=httpx.Response(200, json={"status": "ok"}),
    )
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json",
         "settings", "tsig-out", "set", "k1"],
    )
    assert r.exit_code == 0, r.stdout
    assert route.called


@respx.mock
def test_tsig_out_unset_live(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.delete("https://my.rcodezero.at/api/v2/settings/tsig/out").mock(
        return_value=httpx.Response(204),
    )
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json", "settings", "tsig-out", "unset"],
    )
    assert r.exit_code == 0, r.stdout
    assert route.called
```

- [ ] **Step 6.3 — Run the tests to verify they fail**

Run: `uv run pytest tests/integration/test_settings_write_commands.py -v --no-cov`
Expected: FAIL — `No such command 'secondaries'.`

- [ ] **Step 6.4 — Extend `commands/settings.py`**

Add imports alongside existing ones and append the new Typer subgroups. Full file content:

```python
"""`rc0 settings` — account-level settings (show + Phase 2 setters/unsetters)."""

from __future__ import annotations

from typing import Annotated

import typer

from rc0 import auth as auth_core
from rc0.api import settings as settings_api
from rc0.api import settings_write as settings_write_api
from rc0.app_state import AppState  # noqa: TC001
from rc0.client.dry_run import DryRunResult
from rc0.client.errors import AuthError
from rc0.client.http import Client
from rc0.output import render

app = typer.Typer(
    name="settings",
    help="Manage account-level settings.",
    no_args_is_help=True,
)
secondaries_app = typer.Typer(
    name="secondaries",
    help="Account-wide secondary nameservers.",
    no_args_is_help=True,
)
tsig_in_app = typer.Typer(
    name="tsig-in",
    help="Account-wide inbound TSIG key.",
    no_args_is_help=True,
)
tsig_out_app = typer.Typer(
    name="tsig-out",
    help="Account-wide outbound TSIG key.",
    no_args_is_help=True,
)
app.add_typer(secondaries_app, name="secondaries")
app.add_typer(tsig_in_app, name="tsig-in")
app.add_typer(tsig_out_app, name="tsig-out")


TsigKeyArg = Annotated[str, typer.Argument(help="Preconfigured TSIG key name.")]
IpOpt = Annotated[
    list[str],
    typer.Option(
        "--ip",
        help="Secondary IP (repeatable; at least one required).",
    ),
]


def _client(state: AppState) -> Client:
    token = state.token
    if token is None:
        record = auth_core.load_token(state.profile_name)
        if record is not None:
            token = auth_core.token_of(record)
    if not token:
        raise AuthError(
            "No API token available.",
            hint=f"Run `rc0 auth login` or set RC0_API_TOKEN (profile {state.profile_name!r}).",
        )
    return Client(
        api_url=state.effective_api_url,
        token=token,
        timeout=state.effective_timeout,
    )


def _render(result: DryRunResult | dict[str, object], state: AppState) -> None:
    payload = result.to_dict() if isinstance(result, DryRunResult) else result
    typer.echo(render(payload, fmt=state.effective_output))


@app.command("show")
def show_cmd(ctx: typer.Context) -> None:
    """Show account settings. API: GET /api/v2/settings"""
    state: AppState = ctx.obj
    with _client(state) as client:
        s = settings_api.show_settings(client)
    typer.echo(render(s.model_dump(exclude_none=True), fmt=state.effective_output))


@secondaries_app.command("set")
def secondaries_set(ctx: typer.Context, ips: IpOpt) -> None:
    """Set account-wide secondaries. API: PUT /api/v2/settings/secondaries"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = settings_write_api.set_secondaries(
            client, ips=ips, dry_run=state.dry_run,
        )
    _render(result, state)


@secondaries_app.command("unset")
def secondaries_unset(ctx: typer.Context) -> None:
    """Clear account-wide secondaries. API: DELETE /api/v2/settings/secondaries"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = settings_write_api.unset_secondaries(client, dry_run=state.dry_run)
    _render(result, state)


@tsig_in_app.command("set")
def tsig_in_set(ctx: typer.Context, tsigkey: TsigKeyArg) -> None:
    """Set account-wide inbound TSIG key. API: PUT /api/v2/settings/tsig/in"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = settings_write_api.set_tsig_in(
            client, tsigkey=tsigkey, dry_run=state.dry_run,
        )
    _render(result, state)


@tsig_in_app.command("unset")
def tsig_in_unset(ctx: typer.Context) -> None:
    """Clear account-wide inbound TSIG key. API: DELETE /api/v2/settings/tsig/in"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = settings_write_api.unset_tsig_in(client, dry_run=state.dry_run)
    _render(result, state)


@tsig_out_app.command("set")
def tsig_out_set(ctx: typer.Context, tsigkey: TsigKeyArg) -> None:
    """Set account-wide outbound TSIG key. API: PUT /api/v2/settings/tsig/out"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = settings_write_api.set_tsig_out(
            client, tsigkey=tsigkey, dry_run=state.dry_run,
        )
    _render(result, state)


@tsig_out_app.command("unset")
def tsig_out_unset(ctx: typer.Context) -> None:
    """Clear account-wide outbound TSIG key. API: DELETE /api/v2/settings/tsig/out"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = settings_write_api.unset_tsig_out(client, dry_run=state.dry_run)
    _render(result, state)
```

- [ ] **Step 6.5 — Run the tests to verify they pass**

Run: `uv run pytest tests/integration/test_settings_write_commands.py -v --no-cov`
Expected: PASS (8 tests).

- [ ] **Step 6.6 — Commit**

```bash
git add src/rc0/api/settings_write.py src/rc0/commands/settings.py \
        tests/integration/test_settings_write_commands.py
git commit -m "feat(cli): settings secondaries/tsig-in/tsig-out set/unset"
```

---

## Task 7 — Messages write: ack / ack-all

**Files:**
- Create: `src/rc0/api/messages_write.py`
- Modify: `src/rc0/commands/messages.py`
- Test: `tests/integration/test_messages_write_commands.py`

Semantics for `ack-all` (mission-plan §5):

- Loop: poll → ack the returned ID → poll again, until the API returns an
  empty body `{}`.
- Confirmation: simple `y/N`. `-y` skips. `--dry-run` never acks and emits one
  summary dry-run object (not one per message) because dry-run does not make
  any HTTP calls.

- [ ] **Step 7.1 — Add API wrappers**

```python
# src/rc0/api/messages_write.py
"""Write endpoints against /api/v2/messages."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rc0.api.messages import poll_message
from rc0.client.mutations import execute_mutation

if TYPE_CHECKING:
    from rc0.client.dry_run import DryRunResult
    from rc0.client.http import Client


def ack_message(
    client: Client, *, message_id: int, dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    return execute_mutation(
        client,
        method="DELETE",
        path=f"/api/v2/messages/{message_id}",
        dry_run=dry_run,
        summary=f"Would acknowledge message {message_id}.",
    )


def ack_all(client: Client) -> list[int]:
    """Poll + ack until the queue is empty. Returns the ack'd message IDs.

    Only called on the live path. `--dry-run` shortcircuits in the CLI layer.
    """
    acked: list[int] = []
    while True:
        msg = poll_message(client)
        if msg is None or msg.id is None:
            return acked
        client.delete(f"/api/v2/messages/{msg.id}")
        acked.append(msg.id)
```

- [ ] **Step 7.2 — Write the CLI integration tests**

```python
# tests/integration/test_messages_write_commands.py
"""Messages write-command integration tests."""

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
def test_messages_ack_live(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.delete("https://my.rcodezero.at/api/v2/messages/7").mock(
        return_value=httpx.Response(204),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "messages", "ack", "7"])
    assert r.exit_code == 0, r.stdout
    assert route.called


def test_messages_ack_dry_run(cli: CliRunner, isolated_config: Path) -> None:
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json", "--dry-run", "messages", "ack", "7"],
    )
    assert r.exit_code == 0, r.stdout
    parsed = json.loads(r.stdout)
    assert parsed["dry_run"] is True
    assert parsed["request"]["method"] == "DELETE"
    assert parsed["request"]["url"].endswith("/api/v2/messages/7")


@respx.mock
def test_messages_ack_all_loops_until_empty(
    cli: CliRunner, isolated_config: Path,
) -> None:
    poll = respx.get("https://my.rcodezero.at/api/v2/messages")
    poll.side_effect = [
        httpx.Response(200, json={"id": 1, "domain": "a", "date": "d", "type": "t"}),
        httpx.Response(200, json={"id": 2, "domain": "b", "date": "d", "type": "t"}),
        httpx.Response(200, json={}),
    ]
    del1 = respx.delete("https://my.rcodezero.at/api/v2/messages/1").mock(
        return_value=httpx.Response(204),
    )
    del2 = respx.delete("https://my.rcodezero.at/api/v2/messages/2").mock(
        return_value=httpx.Response(204),
    )
    r = cli.invoke(
        app,
        ["--token", "tk", "-y", "-o", "json", "messages", "ack-all"],
    )
    assert r.exit_code == 0, r.stdout
    assert del1.called and del2.called
    payload = json.loads(r.stdout)
    assert payload["acknowledged"] == [1, 2]


def test_messages_ack_all_yn_declined(
    cli: CliRunner, isolated_config: Path,
) -> None:
    r = cli.invoke(
        app,
        ["--token", "tk", "messages", "ack-all"],
        input="n\n",
    )
    assert r.exit_code == 12, r.stdout


def test_messages_ack_all_dry_run_emits_single_summary(
    cli: CliRunner, isolated_config: Path,
) -> None:
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json", "--dry-run", "messages", "ack-all"],
    )
    assert r.exit_code == 0, r.stdout
    payload = json.loads(r.stdout)
    assert payload["dry_run"] is True
    assert payload["summary"].lower().startswith("would acknowledge")
```

- [ ] **Step 7.3 — Run the tests to verify they fail**

Run: `uv run pytest tests/integration/test_messages_write_commands.py -v --no-cov`
Expected: FAIL — commands not yet wired.

- [ ] **Step 7.4 — Extend `commands/messages.py`**

Append to `src/rc0/commands/messages.py`. Imports to add near the existing ones:

```python
from rc0.api import messages_write as messages_write_api
from rc0.client.dry_run import DryRunResult
from rc0.confirm import confirm_yes_no
```

Append at end of file:

```python
MessageIdArg = Annotated[int, typer.Argument(help="Message ID to acknowledge.")]


def _render_mutation(result: DryRunResult | dict[str, object], state: AppState) -> None:
    payload = result.to_dict() if isinstance(result, DryRunResult) else result
    typer.echo(render(payload, fmt=state.effective_output))


@app.command("ack")
def ack_cmd(ctx: typer.Context, message_id: MessageIdArg) -> None:
    """Acknowledge (delete) one message. API: DELETE /api/v2/messages/{id}"""
    state: AppState = ctx.obj
    with _client(state) as client:
        result = messages_write_api.ack_message(
            client, message_id=message_id, dry_run=state.dry_run,
        )
    _render_mutation(result, state)


@app.command("ack-all")
def ack_all_cmd(ctx: typer.Context) -> None:
    """Loop: poll + ack until the queue is empty. API: GET /messages + DELETE /messages/{id}"""
    state: AppState = ctx.obj
    if state.dry_run:
        # Not a single HTTP call — emit a dry-run envelope with just a summary.
        # The live branch can't know the queue depth without actually draining it.
        typer.echo(
            render(
                {
                    "dry_run": True,
                    "summary": "Would acknowledge every queued account message until empty.",
                    "side_effects": ["drains_message_queue"],
                },
                fmt=state.effective_output,
            ),
        )
        return
    if not state.yes:
        confirm_yes_no("Would acknowledge every queued account message.")
    with _client(state) as client:
        acked = messages_write_api.ack_all(client)
    typer.echo(
        render({"acknowledged": acked, "count": len(acked)}, fmt=state.effective_output),
    )
```

- [ ] **Step 7.5 — Run the tests to verify they pass**

Run: `uv run pytest tests/integration/test_messages_write_commands.py -v --no-cov`
Expected: PASS (5 tests).

- [ ] **Step 7.6 — Commit**

```bash
git add src/rc0/api/messages_write.py src/rc0/commands/messages.py \
        tests/integration/test_messages_write_commands.py
git commit -m "feat(cli): messages ack / ack-all"
```

---

## Task 8 — Clear `PHASE_2_OR_LATER` in the contract test

**Files:**
- Modify: `tests/contract/_expected_v2_gets.py`

`xfr-in show` and `xfr-out show` now exist and have `--help` pages; the contract
test's parametrised branch should include them. Empty the tolerance set.

- [ ] **Step 8.1 — Edit the file**

```python
# tests/contract/_expected_v2_gets.py
"""Map of v2 GET endpoints → CLI command path for the contract test."""

from __future__ import annotations

V2_GET_TO_COMMAND: dict[str, tuple[str, ...]] = {
    "/api/v2/zones": ("zone", "list"),
    "/api/v2/zones/{zone}": ("zone", "show"),
    "/api/v2/zones/{zone}/status": ("zone", "status"),
    "/api/v2/zones/{zone}/rrsets": ("record", "list"),
    "/api/v2/zones/{zone}/inbound": ("zone", "xfr-in", "show"),
    "/api/v2/zones/{zone}/outbound": ("zone", "xfr-out", "show"),
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

# Populated by phases not yet landed. Phase 2 cleared everything that was
# previously deferred.
PHASE_2_OR_LATER: frozenset[str] = frozenset()
```

- [ ] **Step 8.2 — Run the contract tests to verify they still pass**

Run: `uv run pytest tests/contract/ -v --no-cov`
Expected: PASS — including the two rows previously tolerated.

- [ ] **Step 8.3 — Commit**

```bash
git add tests/contract/_expected_v2_gets.py
git commit -m "test(contract): xfr-in/xfr-out show are implemented, drop tolerance"
```

---

## Task 9 — Dry-run parity test

**Files:**
- Create: `tests/unit/test_dry_run_parity.py`

Mission plan §15: for every mutation command, run it twice — once with
`--dry-run`, once against a mock; assert the captured request is byte-identical.
We compare method, URL (with query string), and JSON body. Headers are redacted
in the dry-run and literal in the live request, so we compare the redacted set
after stripping `Authorization`.

- [ ] **Step 9.1 — Write the parity test**

```python
# tests/unit/test_dry_run_parity.py
"""Dry-run vs. live request parity for every Phase-2 mutation."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

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


# (method, url, args, mock-status, mock-body)
PARITY_CASES: list[tuple[str, str, list[str], int, Any]] = [
    (
        "POST", "https://my.rcodezero.at/api/v2/zones",
        ["zone", "create", "example.com", "--type", "master", "--master", "10.0.0.1"],
        201, {"status": "ok"},
    ),
    (
        "PUT", "https://my.rcodezero.at/api/v2/zones/example.com",
        ["zone", "update", "example.com", "--master", "10.0.0.2"],
        200, {"status": "ok"},
    ),
    (
        "PATCH", "https://my.rcodezero.at/api/v2/zones/example.com",
        ["zone", "enable", "example.com"],
        200, {"status": "ok"},
    ),
    (
        "PATCH", "https://my.rcodezero.at/api/v2/zones/example.com",
        ["zone", "disable", "example.com"],
        200, {"status": "ok"},
    ),
    (
        "DELETE", "https://my.rcodezero.at/api/v2/zones/example.com",
        ["-y", "zone", "delete", "example.com"],
        204, None,
    ),
    (
        "POST", "https://my.rcodezero.at/api/v2/zones/example.com/retrieve",
        ["zone", "retrieve", "example.com"],
        200, {"status": "ok"},
    ),
    (
        "POST", "https://my.rcodezero.at/api/v2/zones/example.com/inbound",
        ["zone", "xfr-in", "set", "example.com", "--tsigkey", "k"],
        200, {"status": "ok"},
    ),
    (
        "DELETE", "https://my.rcodezero.at/api/v2/zones/example.com/inbound",
        ["zone", "xfr-in", "unset", "example.com"],
        204, None,
    ),
    (
        "POST", "https://my.rcodezero.at/api/v2/zones/example.com/outbound",
        ["zone", "xfr-out", "set", "example.com", "--tsigkey", "k",
         "--secondary", "10.0.0.1"],
        200, {"status": "ok"},
    ),
    (
        "DELETE", "https://my.rcodezero.at/api/v2/zones/example.com/outbound",
        ["zone", "xfr-out", "unset", "example.com"],
        204, None,
    ),
    (
        "POST", "https://my.rcodezero.at/api/v2/tsig",
        ["tsig", "add", "k1", "--algorithm", "hmac-sha256", "--secret", "abc"],
        201, {"status": "ok"},
    ),
    (
        "PUT", "https://my.rcodezero.at/api/v2/tsig/k1",
        ["tsig", "update", "k1", "--algorithm", "hmac-sha512", "--secret", "xyz"],
        200, {"status": "ok"},
    ),
    (
        "DELETE", "https://my.rcodezero.at/api/v2/tsig/k1",
        ["-y", "tsig", "delete", "k1"],
        204, None,
    ),
    (
        "PUT", "https://my.rcodezero.at/api/v2/settings/secondaries",
        ["settings", "secondaries", "set", "--ip", "10.0.0.1"],
        200, {"status": "ok"},
    ),
    (
        "DELETE", "https://my.rcodezero.at/api/v2/settings/secondaries",
        ["settings", "secondaries", "unset"],
        204, None,
    ),
    (
        "PUT", "https://my.rcodezero.at/api/v2/settings/tsig/in",
        ["settings", "tsig-in", "set", "k1"],
        200, {"status": "ok"},
    ),
    (
        "DELETE", "https://my.rcodezero.at/api/v2/settings/tsig/in",
        ["settings", "tsig-in", "unset"],
        204, None,
    ),
    (
        "PUT", "https://my.rcodezero.at/api/v2/settings/tsig/out",
        ["settings", "tsig-out", "set", "k1"],
        200, {"status": "ok"},
    ),
    (
        "DELETE", "https://my.rcodezero.at/api/v2/settings/tsig/out",
        ["settings", "tsig-out", "unset"],
        204, None,
    ),
    (
        "DELETE", "https://my.rcodezero.at/api/v2/messages/7",
        ["messages", "ack", "7"],
        204, None,
    ),
]


@pytest.mark.parametrize(
    ("method", "url", "args", "status", "body"),
    PARITY_CASES,
    ids=[" ".join(c[2]) for c in PARITY_CASES],
)
@respx.mock
def test_dry_run_parity(
    cli: CliRunner,
    isolated_config: Path,
    method: str,
    url: str,
    args: list[str],
    status: int,
    body: Any,
) -> None:
    # 1. Dry-run: capture what we would send.
    dry = cli.invoke(
        app,
        ["--token", "tk", "-o", "json", "--dry-run", *args],
    )
    assert dry.exit_code == 0, dry.stdout
    dry_payload = json.loads(dry.stdout)
    dry_req = dry_payload["request"]

    # 2. Live: mock the exact URL and method, invoke the same args.
    respx.request(method, url).mock(
        return_value=httpx.Response(
            status,
            json=body if body is not None else {},
        )
    )
    live = cli.invoke(app, ["--token", "tk", "-o", "json", *args])
    assert live.exit_code == 0, live.stdout
    live_request = respx.calls.last.request

    # 3. Compare: method, URL (path+query), JSON body.
    assert dry_req["method"] == method
    assert live_request.method == method
    assert dry_req["url"] == str(live_request.url)
    dry_body = dry_req.get("body")
    live_body = (
        json.loads(live_request.content) if live_request.content else None
    )
    assert dry_body == live_body
```

- [ ] **Step 9.2 — Run the parity tests to verify they pass**

Run: `uv run pytest tests/unit/test_dry_run_parity.py -v --no-cov`
Expected: PASS (20 parametrised cases).

- [ ] **Step 9.3 — Commit**

```bash
git add tests/unit/test_dry_run_parity.py
git commit -m "test: dry-run parity for every Phase 2 mutation"
```

---

## Task 10 — Topic: dry-run.md

**Files:**
- Create: `src/rc0/topics/dry-run.md`
- Modify: `pyproject.toml` (force-include path already includes `src/rc0/topics` — no change needed; verify)

- [ ] **Step 10.1 — Write the topic**

```markdown
# Dry-run

Every rc0 command that changes state supports `--dry-run`. A dry-run never
contacts the API. It prints the HTTP request the command **would** have sent,
in enough detail to reproduce exactly — method, URL, redacted headers, JSON
body, and an English summary.

The exit code is `0` on success (mission-plan §18.1 Option A, matches `gh` and
`terraform plan`). Tell dry-runs apart from real runs by the `"dry_run": true`
field in `-o json` output.

## Human output

```
$ rc0 zone create example.com --type master --master 10.0.0.1 --dry-run
Would create master zone example.com with 1 master IP(s).

  POST https://my.rcodezero.at/api/v2/zones
  Authorization: Bearer ***REDACTED***
  Content-Type: application/json

  {
    "domain": "example.com",
    "type": "master",
    "masters": ["10.0.0.1"]
  }
```

## Machine output

```
$ rc0 zone create example.com --type master --dry-run -o json
{
  "dry_run": true,
  "request": {
    "method": "POST",
    "url": "https://my.rcodezero.at/api/v2/zones",
    "headers": {
      "Authorization": "Bearer ***REDACTED***",
      "Content-Type": "application/json"
    },
    "body": {"domain": "example.com", "type": "master"}
  },
  "summary": "Would create master zone example.com.",
  "side_effects": ["creates_zone"]
}
```

## `--dry-run` vs. `rc0 zone test`

They are different.

- `--dry-run` is a **client-side preview**. No network call. Exits 0.
- `rc0 zone test <domain>` hits `POST /api/v2/zones?test=1`. The API validates
  the would-be zone (domain syntax, conflicts, masters reachability) and returns
  its own errors. The zone is not created.

You can combine them:

```
$ rc0 zone test example.com --type master --dry-run -o json
```

…prints the HTTP request that `zone test` would have sent.

## Confirmations

Destructive commands prompt by default (mission-plan §7). `--dry-run` bypasses
the prompt — there is nothing to destroy — and so does `--yes` / `-y`. Exit
code `12` means the user declined. Exit code `0` means the dry-run printed.

## Parity guarantee

Every rc0 release runs a parity test against its own mutation surface: the
dry-run request body and URL are byte-identical to the request sent on the
live path (see `tests/unit/test_dry_run_parity.py`). If you script against
dry-run output, the real call will look the same.
```

- [ ] **Step 10.2 — Verify `rc0 help dry-run` renders**

Run:
```
uv run rc0 help dry-run | head -5
```
Expected: first heading line `# Dry-run`.

- [ ] **Step 10.3 — Commit**

```bash
git add src/rc0/topics/dry-run.md
git commit -m "docs(topics): dry-run"
```

---

## Task 11 — Full test suite + lint + type-check

Confirm the whole matrix is green before release prep.

- [ ] **Step 11.1 — Run the suite**

Run: `uv run pytest`
Expected: PASS, coverage ≥ 78%. Aim higher; Phase 2 should push total coverage up.

- [ ] **Step 11.2 — Lint**

Run: `uv run ruff check .` → clean; `uv run ruff format --check .` → clean.

If ruff complains about unused imports in `commands/zone.py` (the `ZoneType`
re-export is intentional — exposed for Typer's click_type), suppress with
`# noqa: F401` inline rather than deleting.

- [ ] **Step 11.3 — Type-check**

Run: `uv run mypy`
Expected: clean.

If mypy complains about the Literal narrowing in calls like
`zone_type=zone_type.lower()`, either add a `typing.cast(ZoneType, ...)` or
keep the existing `# type: ignore[arg-type]` — both are acceptable; pick the
one already used in the rest of the module.

- [ ] **Step 11.4 — Commit any fixups**

```bash
git add -u && git commit -m "chore: address lint/type feedback from Phase 2 gate"
# (skip if no changes)
```

---

## Task 12 — Release prep for v0.3.0

**Files:**
- Modify: `src/rc0/__init__.py`, `pyproject.toml`, `CHANGELOG.md`, `CLAUDE.md`

- [ ] **Step 12.1 — Bump the version**

In `src/rc0/__init__.py`:
```python
__version__ = "0.3.0"
```

In `pyproject.toml`:
```toml
version = "0.3.0"
```

- [ ] **Step 12.2 — Raise the coverage floor**

After running the suite in Task 11, read the reported total. If it's ≥ 82%,
bump `fail_under` in `pyproject.toml`:
```toml
fail_under = 82
```
If it dropped below the existing 78 floor, investigate first — Phase 2 should
add coverage, not remove it.

- [ ] **Step 12.3 — Update `CHANGELOG.md`**

Replace the empty `## [Unreleased]` stub with:

```markdown
## [Unreleased]

## [0.3.0] — Mutations with dry-run

### Added
- `rc0 zone create/update/enable/disable/delete/retrieve/test`.
- `rc0 zone xfr-in show/set/unset` and `rc0 zone xfr-out show/set/unset`.
- `rc0 tsig add/update/delete`.
- `rc0 settings secondaries/tsig-in/tsig-out set/unset`.
- `rc0 messages ack/ack-all`.
- `--dry-run` on every new mutation. Exit code 0; machine output carries
  `"dry_run": true`.
- Confirmation prompts for destructive operations: `zone delete` requires
  typing the zone name, `tsig delete` and `messages ack-all` accept a
  simple y/N. `-y` / `--yes` skips; `--dry-run` skips.
- Topic help: `dry-run`.

### Changed
- Contract test `PHASE_2_OR_LATER` tolerance set emptied — both
  `/zones/{zone}/inbound` and `/zones/{zone}/outbound` GET paths are now
  implemented as `rc0 zone xfr-in show` / `rc0 zone xfr-out show`.

### New tests
- `tests/unit/test_dry_run_parity.py` — every Phase 2 mutation runs twice
  (dry-run + mocked live) and the captured HTTP request must be byte-identical.
- Full CLI integration coverage for every new command.
```

Also update the footer link table:
```markdown
[Unreleased]: https://github.com/zoltanf/rc0-cli/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/zoltanf/rc0-cli/releases/tag/v0.3.0
[0.2.0]: https://github.com/zoltanf/rc0-cli/releases/tag/v0.2.0
[0.1.0]: https://github.com/zoltanf/rc0-cli/releases/tag/v0.1.0
```

- [ ] **Step 12.4 — Update `CLAUDE.md` phase status**

Update the phase-status table row for Phase 2 from:
```
| 2 Mutations with dry-run | v0.3.0 | Pending — next up. |
```
to:
```
| 2 Mutations with dry-run | v0.3.0 | **Done** (2026-04-21). Every mutation supports --dry-run; destructive commands prompt; `tests/unit/test_dry_run_parity.py` gates the release. |
```

And flip Phase 3 row to say "Pending — next up."

- [ ] **Step 12.5 — Re-run the full suite one more time**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy`
Expected: all green.

- [ ] **Step 12.6 — Commit release prep**

```bash
git add src/rc0/__init__.py pyproject.toml CHANGELOG.md CLAUDE.md
git commit -m "chore(release): prep v0.3.0"
```

- [ ] **Step 12.7 — Push branch and open PR**

```bash
git push -u origin phase-2-mutations
gh pr create --title "Phase 2: mutations with dry-run (v0.3.0)" --body "$(cat <<'EOF'
## Summary
- Every Phase 2 mutation command (§14) lands with `--dry-run`, confirmation prompts, and matching dry-run/live request parity.
- `tests/unit/test_dry_run_parity.py` is the new mission-plan §15 gate — each mutation sends the same HTTP request in both modes.
- Contract-test `PHASE_2_OR_LATER` cleared: `rc0 zone xfr-in show` / `rc0 zone xfr-out show` now exist.

## Test plan
- [x] `uv run pytest` green, coverage ≥ 78 (target ≥ 82).
- [x] `uv run ruff check .` clean.
- [x] `uv run ruff format --check .` clean.
- [x] `uv run mypy` clean.
- [x] Manual smoke: `uv run rc0 zone create example.com --type master --dry-run -o json` prints the expected envelope.
- [x] Manual smoke: `uv run rc0 zone delete example.com` prompts for typed zone name; wrong answer → exit 12.
EOF
)"
```

- [ ] **Step 12.8 — After CI passes: merge, tag, push tag**

```bash
gh pr merge --squash --delete-branch
git checkout main && git pull
git tag -a v0.3.0 -m "Phase 2 — Mutations with dry-run

Zone create/update/enable/disable/delete/retrieve/test plus xfr-in / xfr-out.
TSIG add/update/delete. Settings secondaries/tsig-in/tsig-out. Messages ack /
ack-all. --dry-run on every mutation; destructive ops prompt for confirmation.
Dry-run/live parity test gates the release."
git push origin v0.3.0
```

Expected: tag visible on GitHub; Phase 2 closed.

---

## Verification summary

After Task 12, every row of mission-plan §14 Phase 2 must be satisfied:

| Check | Source |
|---|---|
| `rc0 zone create/update/enable/disable/retrieve/test` | Task 4 |
| `rc0 zone delete` with typed confirmation | Task 4 |
| `rc0 zone xfr-in/xfr-out set/unset` (and `show`) | Task 4 |
| `rc0 tsig add/update/delete` | Task 5 |
| `rc0 settings secondaries/tsig-in/tsig-out set/unset` | Task 6 |
| `rc0 messages ack`, `rc0 messages ack-all` with confirmation | Task 7 |
| `--dry-run` on every mutation (exit 0, no HTTP) | Task 1 + 3-7 |
| `rc0 zone test` hits `?test=1`, distinct from `--dry-run` | Task 4 |
| Confirmation prompts honour `-y` and `--dry-run` | Task 4, 5, 7 |
| Topic `dry-run` written | Task 10 |
| Dry-run parity test | Task 9 |
| CHANGELOG, version, tag | Task 12 |
| Contract test clean | Task 8 |

---

## Out of scope (deferred to later phases)

- `rc0 record add/update/delete/apply/replace-all/clear` — the hard work
  lives in Phase 3. **RRset mutations require** a significant amount of
  client-side validation; the mutation executor built in Task 1 carries
  straight over.
- `rc0 dnssec sign/unsign/keyrollover/ack-ds/simulate` — Phase 4.
- `rc0 acme *` — Phase 5.
- A human-friendly dry-run text renderer (the `-o table` block sketched in
  §7) — the current renderer emits JSON even in `-o table` mode when data is
  a dict with `"dry_run"` / `"request"` keys. A polished text-mode layout is
  a Phase 7 polish item, not a Phase 2 blocker.

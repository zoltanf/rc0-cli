# Phase 3 — RRsets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the full RRset CRUD surface (`rc0 record add/update/delete/apply/replace-all/clear`) with three input formats (flags, JSON/YAML file, BIND zone file), end-to-end client-side validation, confirmation prompts, and `--dry-run` parity — tagged as **v0.4.0**.

**Architecture:** Three pipelines feed the same two HTTP endpoints (PATCH and PUT on `/api/v2/zones/{zone}/rrsets`):

1. **Parsers** (`rc0.rrsets.parse`) turn each of the three input formats into a list of internal, already-qualified `RRsetChange` Pydantic objects.
2. **Validators** (`rc0.validation.rrsets`) enforce every rule from mission plan §12 (trailing dots auto-fix, TTL floor, CNAME exclusivity, MX priority, A/AAAA IP sanity, PATCH/PUT size caps). They raise `ValidationError` (exit code 7) with actionable hints.
3. **API wrappers** (`rc0.api.rrsets_write`) hand the validated payload to the existing `execute_mutation` dispatcher from Phase 2, so dry-run/live parity falls out for free. `rc0.client.mutations` is **not** modified.

The CLI commands in `rc0.commands.record` are shallow — each is ~20 lines: parse → validate → build body → call `execute_mutation` → render. Confirmation prompts reuse the Phase-2 `confirm_typed` (for zone-level wipes: `apply`, `replace-all`, `clear`) and `confirm_yes_no` (for scoped `delete`).

**Tech Stack:** unchanged. Typer ≥ 0.15, httpx ≥ 0.28, Pydantic v2 (+ `Rc0WriteModel` `extra="forbid"` base from Phase 2), PyYAML (already a dependency), dnspython ≥ 2.7 (already a dependency from Phase 1's `record export -f bind`). No new runtime dependencies.

---

## Mission-plan anchors

- §4 — PATCH/PUT/DELETE rows for `/api/v2/zones/{zone}/rrsets`.
- §5 — command tree for `rc0 record add/update/delete/apply/replace-all/clear`.
- §7 — dry-run + confirmation contract (zone-level destructive ops prompt with typed-zone; other destructive ops y/N; `-y` / `--dry-run` skip).
- §11 — exit codes: 7 for client-side validation; 12 for declined confirmation.
- §12 — **the governing section for this phase** — the three input formats and the full validation list.
- §14 Phase 3 — scope statement.
- §15 — dry-run parity extends to RRset mutations.
- §18.1 — dry-run exits 0.
- §18.4 — record-delete confirmation: always prompt; `-y` for scripts.
- §20 — worked example: `rc0 record apply … --from-file …` with typed-zone confirmation.

## Commands landing in this phase

| Command | HTTP | Body shape | Confirmation | Inputs |
|---|---|---|---|---|
| `rc0 record add <zone>` | PATCH `/api/v2/zones/{zone}/rrsets` | `[{name,type,ttl,changetype:"add",records:[{content}]}]` | no | flags |
| `rc0 record update <zone>` | PATCH same path | `[{..., changetype:"update", ...}]` | no | flags |
| `rc0 record delete <zone>` | PATCH same path | `[{..., changetype:"delete", records: []}]` | y/N | flags |
| `rc0 record apply <zone>` | PATCH same path | `[UpdateRRsetRequest, …]` (mixed changetypes) | typed-zone | `--from-file FILE.{json,yaml,yml}` |
| `rc0 record replace-all <zone>` | PUT `/api/v2/zones/{zone}/rrsets` | `{"rrsets":[{name,type,ttl,records}, …]}` | typed-zone | `--from-file` **or** `--zone-file BIND.zone` |
| `rc0 record clear <zone>` | DELETE `/api/v2/zones/{zone}/rrsets` | (none) | typed-zone | (none) |

Rules that apply to every command:
- `--dry-run` skips the prompt and the network. Exit 0.
- `-y` / `--yes` skips the prompt. Still hits the network.
- `--verbose` (`-v`) surfaces the trailing-dot auto-fix as a warning on stderr (one line per corrected name).
- When `-o json` and a validation error fires, the error renders as the §11 JSON envelope on stderr.

## File structure

**Create:**

- `src/rc0/models/rrset_write.py` — Pydantic request models and the Phase-3 limit constants:
  - `ChangeType = Literal["add", "update", "delete"]`
  - `RecordInput(Rc0WriteModel)` — `content: str`, `disabled: bool = False`
  - `RRsetChange(Rc0WriteModel)` — mirrors `#/components/schemas/UpdateRRsetRequest` (used for PATCH). Fields: `name`, `type`, `ttl`, `changetype`, `records: list[RecordInput]` (default `[]`).
  - `RRsetInput(Rc0WriteModel)` — mirrors `#/components/schemas/RRSets` (used for PUT). Fields: `name`, `type`, `ttl`, `records: list[RecordInput]`.
  - `ReplaceRRsetBody(Rc0WriteModel)` — wraps `{"rrsets": list[RRsetInput]}` for the PUT body.
  - Constants: `PATCH_MAX_RRSETS = 1000`, `PUT_MAX_RRSETS = 3000`, `MIN_TTL = 60`, `CNAME_CONFLICT_TYPES: frozenset[str]` = every RR type that cannot coexist with CNAME at the same label (see Task 2).

- `src/rc0/validation/rrsets.py` — pure-function validators. Every failure raises `rc0.client.errors.ValidationError` with a `hint`. No I/O. Public surface:
  - `qualify_name(raw: str, *, zone: str) -> tuple[str, bool]` — returns `(absolute_fqdn, was_rewritten)`.
  - `validate_ttl(ttl: int, *, context: str) -> None`
  - `validate_content_for_type(type_: str, content: str, *, name: str) -> None` — IP check for A/AAAA, MX priority check for MX.
  - `enforce_cname_exclusivity(changes: list[RRsetChange]) -> None` — rejects intra-batch conflicts.
  - `enforce_cname_exclusivity_replacement(rrsets: list[RRsetInput]) -> None` — same rule for PUT.
  - `validate_changes(changes: list[RRsetChange]) -> None` — the PATCH pipeline entry point; ≤ `PATCH_MAX_RRSETS`, runs per-change validators.
  - `validate_replacement(rrsets: list[RRsetInput]) -> None` — the PUT pipeline entry point; ≤ `PUT_MAX_RRSETS`.

- `src/rc0/rrsets/__init__.py` — empty package marker with a module docstring.
- `src/rc0/rrsets/parse.py` — three parsers producing Pydantic objects. Public surface:
  - `from_flags(*, name: str, type_: str, ttl: int, contents: list[str], disabled: bool, changetype: ChangeType, zone: str, verbose: int, warn: Callable[[str], None]) -> RRsetChange`
  - `from_file(path: Path, *, zone: str, verbose: int, warn: Callable[[str], None]) -> list[RRsetChange]` — accepts `.json`, `.yaml`, `.yml`; format sniffed by suffix.
  - `from_zonefile(path: Path, *, zone: str) -> list[RRsetInput]` — dnspython-backed BIND parser; outputs PUT-shape rrsets (no `changetype`).
  - Every parser delegates the trailing-dot auto-fix to `validation.rrsets.qualify_name`, emitting a stderr line per corrected label when `verbose >= 1`.

- `src/rc0/api/rrsets_write.py` — thin HTTP wrappers routed through `rc0.client.mutations.execute_mutation`. Public surface:
  - `patch_rrsets(client, *, zone: str, changes: list[RRsetChange], dry_run: bool, summary: str, side_effects: list[str] | None = None) -> DryRunResult | dict`
  - `put_rrsets(client, *, zone: str, rrsets: list[RRsetInput], dry_run: bool, summary: str) -> DryRunResult | dict`
  - `clear_rrsets(client, *, zone: str, dry_run: bool) -> DryRunResult | dict`

- `src/rc0/topics/rrset-format.md` — mission-plan §10 "rrset-format" topic.

- Unit tests:
  - `tests/unit/test_rrset_models.py`
  - `tests/unit/test_rrset_validate.py`
  - `tests/unit/test_rrset_parse_flags.py`
  - `tests/unit/test_rrset_parse_file.py`
  - `tests/unit/test_rrset_parse_zonefile.py`
  - `tests/unit/test_rrsets_write_api.py`

- Integration test:
  - `tests/integration/test_record_write_commands.py` — one module covering all six new commands end-to-end through Typer's `CliRunner`, with `respx` mocking and `confirm_typed`/`confirm_yes_no` driven via `input=`.

**Modify:**

- `src/rc0/commands/record.py` — append six subcommands to the existing Typer app (`list`, `export` remain untouched).
- `src/rc0/validation/__init__.py` — add a module docstring pointer to `rc0.validation.rrsets`.
- `tests/unit/test_dry_run_parity.py` — extend `PARITY_CASES` with six new rows (`record add/update/delete/apply/replace-all/clear`).
- `CHANGELOG.md` — `[0.4.0] — RRsets` section.
- `CLAUDE.md` — flip Phase 3 row to **Done**, Phase 4 row to **Pending — next up**. Update the coverage paragraph if the floor moves.
- `src/rc0/__init__.py`, `pyproject.toml` — bump `__version__` and `[project] version` to `"0.4.0"`.

## Public interfaces (referenced across tasks)

```python
# src/rc0/models/rrset_write.py
from __future__ import annotations

from typing import Literal

from pydantic import Field

from rc0.models.common import Rc0WriteModel

ChangeType = Literal["add", "update", "delete"]

PATCH_MAX_RRSETS: int = 1000
PUT_MAX_RRSETS: int = 3000
MIN_TTL: int = 60

# Types that cannot coexist with CNAME at the same label. SOA/DNSKEY/NSEC*/RRSIG
# are apex-managed by the provider and not user-writable via this API, but we
# still list them so the validator can produce a single consistent message.
CNAME_CONFLICT_TYPES: frozenset[str] = frozenset(
    {
        "A", "AAAA", "AFSDB", "ALIAS", "CAA", "CERT", "DNAME", "DS", "HINFO",
        "HTTPS", "LOC", "MX", "NAPTR", "NS", "PTR", "RP", "SMIMEA", "SPF",
        "SRV", "SSHFP", "SVCB", "TLSA", "TXT", "URI",
    },
)


class RecordInput(Rc0WriteModel):
    content: str
    disabled: bool = False


class RRsetChange(Rc0WriteModel):
    """One row in a PATCH /rrsets body (mirrors UpdateRRsetRequest)."""

    name: str
    type: str
    ttl: int
    changetype: ChangeType
    records: list[RecordInput] = Field(default_factory=list)


class RRsetInput(Rc0WriteModel):
    """One row in a PUT /rrsets body (mirrors RRSets)."""

    name: str
    type: str
    ttl: int
    records: list[RecordInput] = Field(default_factory=list)


class ReplaceRRsetBody(Rc0WriteModel):
    """PUT /rrsets request body (mirrors ReplaceRRsetRequest)."""

    rrsets: list[RRsetInput] = Field(default_factory=list)
```

```python
# src/rc0/validation/rrsets.py (public surface — implementation in Task 2)
def qualify_name(raw: str, *, zone: str) -> tuple[str, bool]: ...
def validate_ttl(ttl: int, *, context: str) -> None: ...
def validate_content_for_type(type_: str, content: str, *, name: str) -> None: ...
def enforce_cname_exclusivity(changes: list[RRsetChange]) -> None: ...
def enforce_cname_exclusivity_replacement(rrsets: list[RRsetInput]) -> None: ...
def validate_changes(changes: list[RRsetChange]) -> None: ...
def validate_replacement(rrsets: list[RRsetInput]) -> None: ...
```

```python
# src/rc0/api/rrsets_write.py (public surface — implementation in Task 6)
def patch_rrsets(
    client: Client, *, zone: str, changes: list[RRsetChange],
    dry_run: bool, summary: str, side_effects: list[str] | None = None,
) -> DryRunResult | dict[str, Any]: ...

def put_rrsets(
    client: Client, *, zone: str, rrsets: list[RRsetInput],
    dry_run: bool, summary: str,
) -> DryRunResult | dict[str, Any]: ...

def clear_rrsets(
    client: Client, *, zone: str, dry_run: bool,
) -> DryRunResult | dict[str, Any]: ...
```

---

## Task 1 — Request models and constants

**Files:**
- Create: `src/rc0/models/rrset_write.py`
- Test: `tests/unit/test_rrset_models.py`

- [ ] **Step 1.1 — Write the failing test**

```python
# tests/unit/test_rrset_models.py
"""Tests for Phase-3 RRset request models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from rc0.models.rrset_write import (
    CNAME_CONFLICT_TYPES,
    MIN_TTL,
    PATCH_MAX_RRSETS,
    PUT_MAX_RRSETS,
    RecordInput,
    ReplaceRRsetBody,
    RRsetChange,
    RRsetInput,
)


def test_limit_constants_match_mission_plan() -> None:
    assert PATCH_MAX_RRSETS == 1000
    assert PUT_MAX_RRSETS == 3000
    assert MIN_TTL == 60


def test_cname_conflict_types_includes_core_rr_types() -> None:
    for t in ("A", "AAAA", "MX", "TXT", "NS", "SRV"):
        assert t in CNAME_CONFLICT_TYPES
    assert "CNAME" not in CNAME_CONFLICT_TYPES


def test_rrset_change_roundtrips() -> None:
    change = RRsetChange(
        name="www.example.com.",
        type="A",
        ttl=3600,
        changetype="add",
        records=[RecordInput(content="10.0.0.1")],
    )
    assert change.model_dump() == {
        "name": "www.example.com.",
        "type": "A",
        "ttl": 3600,
        "changetype": "add",
        "records": [{"content": "10.0.0.1", "disabled": False}],
    }


def test_rrset_change_delete_allows_empty_records() -> None:
    change = RRsetChange(
        name="old.example.com.", type="A", ttl=3600, changetype="delete",
    )
    assert change.records == []


def test_rrset_change_rejects_unknown_changetype() -> None:
    with pytest.raises(PydanticValidationError):
        RRsetChange(
            name="x.example.com.",
            type="A",
            ttl=3600,
            changetype="replace",  # type: ignore[arg-type]
        )


def test_rrset_change_rejects_extra_fields() -> None:
    # Rc0WriteModel has extra="forbid"; typos fail loudly.
    with pytest.raises(PydanticValidationError):
        RRsetChange(
            name="x.example.com.",
            type="A",
            ttl=3600,
            changetype="add",
            note="this field does not belong",  # type: ignore[call-arg]
        )


def test_rrset_input_shape_matches_put_body_row() -> None:
    row = RRsetInput(
        name="example.com.",
        type="MX",
        ttl=3600,
        records=[RecordInput(content="10 mail.example.com.")],
    )
    # PUT body rows never carry `changetype`.
    assert "changetype" not in row.model_dump()


def test_replace_rrset_body_roundtrips() -> None:
    body = ReplaceRRsetBody(
        rrsets=[
            RRsetInput(
                name="example.com.",
                type="SOA",
                ttl=3600,
                records=[
                    RecordInput(
                        content="ns1.example.com. admin.example.com. 1 7200 3600 1209600 3600",
                    ),
                ],
            ),
        ],
    )
    dumped = body.model_dump()
    assert "rrsets" in dumped
    assert dumped["rrsets"][0]["type"] == "SOA"
```

- [ ] **Step 1.2 — Run the test to verify it fails**

Run: `uv run pytest tests/unit/test_rrset_models.py -v --no-cov`
Expected: FAIL with `ModuleNotFoundError: No module named 'rc0.models.rrset_write'`.

- [ ] **Step 1.3 — Implement the models**

```python
# src/rc0/models/rrset_write.py
"""Pydantic request bodies and client-side limits for the /rrsets endpoints.

These models mirror the v2 OpenAPI schemas:

* :class:`RRsetChange` ↔ ``UpdateRRsetRequest`` (used in PATCH body array).
* :class:`RRsetInput`  ↔ ``RRSets``             (used in PUT body array).
* :class:`ReplaceRRsetBody` ↔ ``ReplaceRRsetRequest``.

Mission plan §12 pins the size and TTL limits, so they live here as module-level
constants alongside the models that use them.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from rc0.models.common import Rc0WriteModel

ChangeType = Literal["add", "update", "delete"]

PATCH_MAX_RRSETS: int = 1000
PUT_MAX_RRSETS: int = 3000
MIN_TTL: int = 60

CNAME_CONFLICT_TYPES: frozenset[str] = frozenset(
    {
        "A", "AAAA", "AFSDB", "ALIAS", "CAA", "CERT", "DNAME", "DS", "HINFO",
        "HTTPS", "LOC", "MX", "NAPTR", "NS", "PTR", "RP", "SMIMEA", "SPF",
        "SRV", "SSHFP", "SVCB", "TLSA", "TXT", "URI",
    },
)


class RecordInput(Rc0WriteModel):
    content: str
    disabled: bool = False


class RRsetChange(Rc0WriteModel):
    name: str
    type: str
    ttl: int
    changetype: ChangeType
    records: list[RecordInput] = Field(default_factory=list)


class RRsetInput(Rc0WriteModel):
    name: str
    type: str
    ttl: int
    records: list[RecordInput] = Field(default_factory=list)


class ReplaceRRsetBody(Rc0WriteModel):
    rrsets: list[RRsetInput] = Field(default_factory=list)
```

- [ ] **Step 1.4 — Run the test to verify it passes**

Run: `uv run pytest tests/unit/test_rrset_models.py -v --no-cov`
Expected: PASS (8 tests).

- [ ] **Step 1.5 — Commit**

```bash
git checkout -b phase-3-rrsets
git add src/rc0/models/rrset_write.py tests/unit/test_rrset_models.py
git commit -m "feat(models): Phase 3 RRset request models + §12 limits"
```

---

## Task 2 — Client-side validators

**Files:**
- Create: `src/rc0/validation/rrsets.py`
- Modify: `src/rc0/validation/__init__.py` (docstring only)
- Test: `tests/unit/test_rrset_validate.py`

- [ ] **Step 2.1 — Write the failing test**

```python
# tests/unit/test_rrset_validate.py
"""Tests for rc0.validation.rrsets."""

from __future__ import annotations

import pytest

from rc0.client.errors import ValidationError
from rc0.models.rrset_write import (
    PATCH_MAX_RRSETS,
    PUT_MAX_RRSETS,
    RecordInput,
    RRsetChange,
    RRsetInput,
)
from rc0.validation.rrsets import (
    enforce_cname_exclusivity,
    qualify_name,
    validate_changes,
    validate_content_for_type,
    validate_replacement,
    validate_ttl,
)


def test_qualify_name_relative_gets_zone_appended() -> None:
    out, rewritten = qualify_name("www", zone="example.com")
    assert out == "www.example.com."
    assert rewritten is True


def test_qualify_name_at_means_apex() -> None:
    out, rewritten = qualify_name("@", zone="example.com")
    assert out == "example.com."
    assert rewritten is True


def test_qualify_name_absolute_without_dot_gets_dot() -> None:
    out, rewritten = qualify_name("www.example.com", zone="example.com")
    assert out == "www.example.com."
    assert rewritten is True


def test_qualify_name_already_absolute_noop() -> None:
    out, rewritten = qualify_name("www.example.com.", zone="example.com")
    assert out == "www.example.com."
    assert rewritten is False


def test_qualify_name_zone_with_trailing_dot_accepted() -> None:
    out, rewritten = qualify_name("www", zone="example.com.")
    assert out == "www.example.com."
    assert rewritten is True


def test_qualify_name_rejects_empty() -> None:
    with pytest.raises(ValidationError):
        qualify_name("", zone="example.com")


def test_validate_ttl_below_floor_raises() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_ttl(30, context="www.example.com. A")
    assert "60" in exc.value.message


def test_validate_ttl_at_floor_ok() -> None:
    validate_ttl(60, context="x")


def test_validate_content_a_accepts_ipv4() -> None:
    validate_content_for_type("A", "10.0.0.1", name="www.example.com.")


def test_validate_content_a_rejects_non_ipv4() -> None:
    with pytest.raises(ValidationError):
        validate_content_for_type("A", "not-an-ip", name="www.example.com.")
    with pytest.raises(ValidationError):
        validate_content_for_type("A", "2001:db8::1", name="www.example.com.")


def test_validate_content_aaaa_accepts_ipv6() -> None:
    validate_content_for_type("AAAA", "2001:db8::1", name="www.example.com.")


def test_validate_content_aaaa_rejects_ipv4() -> None:
    with pytest.raises(ValidationError):
        validate_content_for_type("AAAA", "10.0.0.1", name="www.example.com.")


def test_validate_content_mx_requires_priority() -> None:
    validate_content_for_type("MX", "10 mail.example.com.", name="example.com.")
    with pytest.raises(ValidationError):
        validate_content_for_type("MX", "mail.example.com.", name="example.com.")
    with pytest.raises(ValidationError):
        validate_content_for_type("MX", "high mail.example.com.", name="example.com.")


def test_enforce_cname_exclusivity_rejects_conflict() -> None:
    changes = [
        RRsetChange(
            name="www.example.com.", type="CNAME", ttl=3600, changetype="add",
            records=[RecordInput(content="host.example.com.")],
        ),
        RRsetChange(
            name="www.example.com.", type="A", ttl=3600, changetype="add",
            records=[RecordInput(content="10.0.0.1")],
        ),
    ]
    with pytest.raises(ValidationError) as exc:
        enforce_cname_exclusivity(changes)
    assert "CNAME" in exc.value.message


def test_enforce_cname_exclusivity_allows_delete_of_other_type() -> None:
    # Moving a label from A to CNAME in a single PATCH should be allowed when
    # the existing A is deleted in the same batch.
    changes = [
        RRsetChange(
            name="www.example.com.", type="A", ttl=3600, changetype="delete",
        ),
        RRsetChange(
            name="www.example.com.", type="CNAME", ttl=3600, changetype="add",
            records=[RecordInput(content="host.example.com.")],
        ),
    ]
    enforce_cname_exclusivity(changes)


def test_validate_changes_enforces_patch_limit() -> None:
    many = [
        RRsetChange(
            name=f"n{i}.example.com.", type="A", ttl=3600, changetype="add",
            records=[RecordInput(content="10.0.0.1")],
        )
        for i in range(PATCH_MAX_RRSETS + 1)
    ]
    with pytest.raises(ValidationError) as exc:
        validate_changes(many)
    assert "1000" in exc.value.message


def test_validate_replacement_enforces_put_limit() -> None:
    many = [
        RRsetInput(
            name=f"n{i}.example.com.", type="A", ttl=3600,
            records=[RecordInput(content="10.0.0.1")],
        )
        for i in range(PUT_MAX_RRSETS + 1)
    ]
    with pytest.raises(ValidationError) as exc:
        validate_replacement(many)
    assert "3000" in exc.value.message


def test_validate_changes_runs_per_change_validators() -> None:
    changes = [
        RRsetChange(
            name="www.example.com.", type="A", ttl=10, changetype="add",
            records=[RecordInput(content="10.0.0.1")],
        ),
    ]
    with pytest.raises(ValidationError):
        validate_changes(changes)


def test_validate_changes_delete_skips_content_validation() -> None:
    # A delete with no records shouldn't trip IP validation.
    changes = [
        RRsetChange(
            name="www.example.com.", type="A", ttl=3600, changetype="delete",
        ),
    ]
    validate_changes(changes)
```

- [ ] **Step 2.2 — Run the test to verify it fails**

Run: `uv run pytest tests/unit/test_rrset_validate.py -v --no-cov`
Expected: FAIL with `ModuleNotFoundError: No module named 'rc0.validation.rrsets'`.

- [ ] **Step 2.3 — Implement the validators**

```python
# src/rc0/validation/rrsets.py
"""Client-side validators for /rrsets mutations (mission plan §12).

All public functions raise :class:`rc0.client.errors.ValidationError` on
failure, which maps to exit code 7 (§11). The messages carry an actionable
``hint``.

The validators are pure: no I/O, no HTTP. This lets the CLI fail fast before
spending a network round-trip, and keeps the logic trivially unit-testable.
"""

from __future__ import annotations

import ipaddress
import re

from rc0.client.errors import ValidationError
from rc0.models.rrset_write import (
    CNAME_CONFLICT_TYPES,
    MIN_TTL,
    PATCH_MAX_RRSETS,
    PUT_MAX_RRSETS,
    RRsetChange,
    RRsetInput,
)

_MX_PATTERN = re.compile(r"^\s*(\d+)\s+(\S.*?)\s*$")


def qualify_name(raw: str, *, zone: str) -> tuple[str, bool]:
    """Return ``(fqdn, was_rewritten)`` for a user-supplied record name.

    Rules (mission plan §12):
    * ``@`` → zone apex.
    * Name without trailing dot that does not end in the zone → append ``.<zone>.``.
    * Name without trailing dot that does end in the zone → append ``.``.
    * Name already absolute (``foo.example.com.``) → pass through, no rewrite.
    """
    if not raw:
        raise ValidationError(
            "RRset name is required.",
            hint="Use --name with the leaf label, FQDN, or @ for the apex.",
        )
    zone_apex = zone.rstrip(".") + "."
    if raw == "@":
        return zone_apex, True
    if raw.endswith("."):
        return raw, False
    if raw.endswith(zone.rstrip(".")):
        return raw + ".", True
    return f"{raw}.{zone_apex}", True


def validate_ttl(ttl: int, *, context: str) -> None:
    if ttl < MIN_TTL:
        raise ValidationError(
            f"TTL {ttl} for {context} is below the provider minimum ({MIN_TTL}).",
            hint=f"Set --ttl to {MIN_TTL} or higher.",
        )


def validate_content_for_type(type_: str, content: str, *, name: str) -> None:
    t = type_.upper()
    if t == "A":
        try:
            ipaddress.IPv4Address(content)
        except (ipaddress.AddressValueError, ValueError) as exc:
            raise ValidationError(
                f"Invalid IPv4 address {content!r} for A record {name!r}.",
                hint="Use a dotted-quad IPv4, e.g. 10.0.0.1.",
            ) from exc
    elif t == "AAAA":
        try:
            ipaddress.IPv6Address(content)
        except (ipaddress.AddressValueError, ValueError) as exc:
            raise ValidationError(
                f"Invalid IPv6 address {content!r} for AAAA record {name!r}.",
                hint="Use a colon-hex IPv6, e.g. 2001:db8::1.",
            ) from exc
    elif t == "MX":
        match = _MX_PATTERN.match(content)
        if match is None:
            raise ValidationError(
                f"MX content {content!r} for {name!r} must be "
                f"`<priority> <exchange>`, e.g. `10 mail.example.com.`.",
                hint="Prefix the exchange with a numeric priority.",
            )


def enforce_cname_exclusivity(changes: list[RRsetChange]) -> None:
    """Reject any add/update that puts CNAME and a conflicting type on the same label.

    Cross-batch conflicts (CNAME already present on the server) are left to the
    API; we only see intra-batch collisions here.
    """
    per_name_live: dict[str, set[str]] = {}
    for change in changes:
        if change.changetype == "delete":
            continue
        per_name_live.setdefault(change.name, set()).add(change.type.upper())
    for name, types in per_name_live.items():
        if "CNAME" in types and any(t in CNAME_CONFLICT_TYPES for t in types):
            offenders = sorted(types - {"CNAME"})
            raise ValidationError(
                f"Label {name!r} cannot hold a CNAME together with {offenders!r}.",
                hint="CNAMEs must be the only record at a label (RFC 1912 §2.4). "
                     "Delete the other types in the same batch or choose a "
                     "different label.",
            )


def enforce_cname_exclusivity_replacement(rrsets: list[RRsetInput]) -> None:
    per_name: dict[str, set[str]] = {}
    for r in rrsets:
        per_name.setdefault(r.name, set()).add(r.type.upper())
    for name, types in per_name.items():
        if "CNAME" in types and any(t in CNAME_CONFLICT_TYPES for t in types):
            offenders = sorted(types - {"CNAME"})
            raise ValidationError(
                f"Label {name!r} cannot hold a CNAME together with {offenders!r}.",
                hint="CNAMEs must be the only record at a label (RFC 1912 §2.4).",
            )


def validate_changes(changes: list[RRsetChange]) -> None:
    if len(changes) > PATCH_MAX_RRSETS:
        raise ValidationError(
            f"A single PATCH may carry at most {PATCH_MAX_RRSETS} rrsets "
            f"(got {len(changes)}).",
            hint="Split the batch, or use `rc0 record replace-all` which allows "
                 f"up to {PUT_MAX_RRSETS} rrsets in one PUT.",
        )
    for change in changes:
        context = f"{change.name} {change.type}"
        validate_ttl(change.ttl, context=context)
        if change.changetype != "delete":
            for record in change.records:
                validate_content_for_type(change.type, record.content, name=change.name)
    enforce_cname_exclusivity(changes)


def validate_replacement(rrsets: list[RRsetInput]) -> None:
    if len(rrsets) > PUT_MAX_RRSETS:
        raise ValidationError(
            f"A single PUT may carry at most {PUT_MAX_RRSETS} rrsets "
            f"(got {len(rrsets)}).",
            hint="Split the zone transfer or trim unchanged rrsets client-side.",
        )
    for rrset in rrsets:
        context = f"{rrset.name} {rrset.type}"
        validate_ttl(rrset.ttl, context=context)
        for record in rrset.records:
            validate_content_for_type(rrset.type, record.content, name=rrset.name)
    enforce_cname_exclusivity_replacement(rrsets)
```

- [ ] **Step 2.4 — Wire the validation package docstring**

```python
# src/rc0/validation/__init__.py
"""Client-side validation (§12).

Phase 3 populated :mod:`rc0.validation.rrsets` with the rrset validators. Keep
new phase-specific validators in their own submodules; ``__init__`` stays
intentionally empty so imports like ``from rc0.validation.rrsets import …``
work without pulling in unrelated code.
"""
```

- [ ] **Step 2.5 — Run the test to verify it passes**

Run: `uv run pytest tests/unit/test_rrset_validate.py -v --no-cov`
Expected: PASS (17 tests).

- [ ] **Step 2.6 — Commit**

```bash
git add src/rc0/validation/rrsets.py src/rc0/validation/__init__.py \
        tests/unit/test_rrset_validate.py
git commit -m "feat(validation): client-side RRset validators (§12)"
```

---

## Task 3 — Flag-based parser

**Files:**
- Create: `src/rc0/rrsets/__init__.py`, `src/rc0/rrsets/parse.py` (partial — `from_flags` only)
- Test: `tests/unit/test_rrset_parse_flags.py`

- [ ] **Step 3.1 — Write the failing test**

```python
# tests/unit/test_rrset_parse_flags.py
"""Tests for rc0.rrsets.parse.from_flags."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from rc0.client.errors import ValidationError
from rc0.rrsets.parse import from_flags


def _warn_sink() -> tuple[list[str], Callable[[str], None]]:
    captured: list[str] = []
    return captured, captured.append


def test_from_flags_single_content() -> None:
    _, sink = _warn_sink()
    change = from_flags(
        name="www",
        type_="A",
        ttl=3600,
        contents=["10.0.0.1"],
        disabled=False,
        changetype="add",
        zone="example.com",
        verbose=0,
        warn=sink,
    )
    assert change.name == "www.example.com."
    assert change.type == "A"
    assert change.ttl == 3600
    assert change.changetype == "add"
    assert [r.content for r in change.records] == ["10.0.0.1"]
    assert [r.disabled for r in change.records] == [False]


def test_from_flags_multiple_contents_aggregate() -> None:
    _, sink = _warn_sink()
    change = from_flags(
        name="www.example.com.",
        type_="A",
        ttl=3600,
        contents=["10.0.0.1", "10.0.0.2"],
        disabled=False,
        changetype="add",
        zone="example.com",
        verbose=0,
        warn=sink,
    )
    assert [r.content for r in change.records] == ["10.0.0.1", "10.0.0.2"]


def test_from_flags_delete_allows_empty_contents() -> None:
    _, sink = _warn_sink()
    change = from_flags(
        name="old",
        type_="A",
        ttl=3600,
        contents=[],
        disabled=False,
        changetype="delete",
        zone="example.com",
        verbose=0,
        warn=sink,
    )
    assert change.records == []


def test_from_flags_add_requires_contents() -> None:
    _, sink = _warn_sink()
    with pytest.raises(ValidationError):
        from_flags(
            name="www", type_="A", ttl=3600, contents=[],
            disabled=False, changetype="add", zone="example.com",
            verbose=0, warn=sink,
        )


def test_from_flags_trailing_dot_warn_emitted_in_verbose() -> None:
    captured, sink = _warn_sink()
    from_flags(
        name="www", type_="A", ttl=3600, contents=["10.0.0.1"],
        disabled=False, changetype="add", zone="example.com",
        verbose=1, warn=sink,
    )
    assert any("www.example.com." in line for line in captured)


def test_from_flags_no_warn_when_absolute() -> None:
    captured, sink = _warn_sink()
    from_flags(
        name="www.example.com.", type_="A", ttl=3600, contents=["10.0.0.1"],
        disabled=False, changetype="add", zone="example.com",
        verbose=1, warn=sink,
    )
    assert captured == []
```

- [ ] **Step 3.2 — Run the test to verify it fails**

Run: `uv run pytest tests/unit/test_rrset_parse_flags.py -v --no-cov`
Expected: FAIL with `ModuleNotFoundError: No module named 'rc0.rrsets'`.

- [ ] **Step 3.3 — Create the package + flag parser**

```python
# src/rc0/rrsets/__init__.py
"""Phase-3 RRset input pipeline.

``parse.py`` turns each of the three input formats specified in mission-plan
§12 — flags, JSON/YAML files, and BIND zone files — into Pydantic rrset models
ready for :mod:`rc0.api.rrsets_write`.

Validation (client-side RRset rules) lives in :mod:`rc0.validation.rrsets`.
This package only produces models; callers must run the validators before
dispatching the request.
"""
```

```python
# src/rc0/rrsets/parse.py (flags path only — file/zonefile land in Tasks 4-5)
"""Parsers that turn user input into :class:`RRsetChange`/:class:`RRsetInput`.

Every parser:

* Qualifies relative names via :func:`rc0.validation.rrsets.qualify_name`.
* Emits a one-line warning per auto-qualified name to ``warn`` when
  ``verbose >= 1`` — matches mission-plan §12 ("auto-fix, warn in verbose").
* Produces already-typed Pydantic models; the caller runs the batch validators
  (PATCH/PUT size, CNAME exclusivity) after aggregation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rc0.client.errors import ValidationError
from rc0.models.rrset_write import (
    ChangeType,
    RecordInput,
    RRsetChange,
)
from rc0.validation.rrsets import qualify_name

if TYPE_CHECKING:
    from collections.abc import Callable


def _maybe_warn(
    *, raw: str, qualified: str, rewritten: bool, verbose: int,
    warn: Callable[[str], None],
) -> None:
    if rewritten and verbose >= 1:
        warn(f"auto-qualified name {raw!r} → {qualified!r}")


def from_flags(
    *,
    name: str,
    type_: str,
    ttl: int,
    contents: list[str],
    disabled: bool,
    changetype: ChangeType,
    zone: str,
    verbose: int,
    warn: Callable[[str], None],
) -> RRsetChange:
    """Build a single-row PATCH change from CLI flag inputs."""
    qualified, rewritten = qualify_name(name, zone=zone)
    _maybe_warn(
        raw=name, qualified=qualified, rewritten=rewritten,
        verbose=verbose, warn=warn,
    )
    if changetype != "delete" and not contents:
        raise ValidationError(
            f"`record {changetype}` requires at least one --content value.",
            hint="Pass one --content per record, or use `record delete` to "
                 "drop the whole RRset.",
        )
    return RRsetChange(
        name=qualified,
        type=type_.upper(),
        ttl=ttl,
        changetype=changetype,
        records=[RecordInput(content=c, disabled=disabled) for c in contents],
    )
```

- [ ] **Step 3.4 — Run the test to verify it passes**

Run: `uv run pytest tests/unit/test_rrset_parse_flags.py -v --no-cov`
Expected: PASS (6 tests).

- [ ] **Step 3.5 — Commit**

```bash
git add src/rc0/rrsets/__init__.py src/rc0/rrsets/parse.py \
        tests/unit/test_rrset_parse_flags.py
git commit -m "feat(rrsets): flag-based parser for PATCH changes"
```

---

## Task 4 — JSON/YAML file parser (`--from-file`)

**Files:**
- Modify: `src/rc0/rrsets/parse.py` (add `from_file`)
- Test: `tests/unit/test_rrset_parse_file.py`

- [ ] **Step 4.1 — Write the failing test**

```python
# tests/unit/test_rrset_parse_file.py
"""Tests for rc0.rrsets.parse.from_file (JSON / YAML)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from rc0.client.errors import ValidationError
from rc0.rrsets.parse import from_file


def _warn_sink() -> tuple[list[str], Callable[[str], None]]:
    captured: list[str] = []
    return captured, captured.append


def test_from_file_yaml(tmp_path: Path) -> None:
    src = tmp_path / "changes.yaml"
    src.write_text(
        """- name: www.example.com.
  type: A
  ttl: 3600
  changetype: add
  records:
    - content: 10.0.0.1
    - content: 10.0.0.2
- name: old.example.com.
  type: A
  ttl: 3600
  changetype: delete
""",
    )
    _, sink = _warn_sink()
    changes = from_file(src, zone="example.com", verbose=0, warn=sink)
    assert len(changes) == 2
    assert changes[0].changetype == "add"
    assert [r.content for r in changes[0].records] == ["10.0.0.1", "10.0.0.2"]
    assert changes[1].changetype == "delete"
    assert changes[1].records == []


def test_from_file_json(tmp_path: Path) -> None:
    src = tmp_path / "changes.json"
    src.write_text(
        """[
  {"name": "www.example.com.", "type": "A", "ttl": 3600,
   "changetype": "add", "records": [{"content": "10.0.0.1"}]}
]""",
    )
    _, sink = _warn_sink()
    changes = from_file(src, zone="example.com", verbose=0, warn=sink)
    assert len(changes) == 1
    assert changes[0].records[0].content == "10.0.0.1"


def test_from_file_qualifies_relative_names_and_warns(tmp_path: Path) -> None:
    src = tmp_path / "changes.yaml"
    src.write_text(
        "- name: www\n  type: A\n  ttl: 3600\n  changetype: add\n"
        "  records:\n    - content: 10.0.0.1\n",
    )
    captured, sink = _warn_sink()
    changes = from_file(src, zone="example.com", verbose=1, warn=sink)
    assert changes[0].name == "www.example.com."
    assert any("www.example.com." in line for line in captured)


def test_from_file_rejects_top_level_dict(tmp_path: Path) -> None:
    src = tmp_path / "wrong.yaml"
    src.write_text("name: www.example.com.\ntype: A\n")
    _, sink = _warn_sink()
    with pytest.raises(ValidationError) as exc:
        from_file(src, zone="example.com", verbose=0, warn=sink)
    assert "list" in exc.value.message.lower()


def test_from_file_unknown_extension(tmp_path: Path) -> None:
    src = tmp_path / "changes.txt"
    src.write_text("[]")
    _, sink = _warn_sink()
    with pytest.raises(ValidationError) as exc:
        from_file(src, zone="example.com", verbose=0, warn=sink)
    assert "extension" in exc.value.message.lower()


def test_from_file_missing_required_field(tmp_path: Path) -> None:
    src = tmp_path / "bad.yaml"
    src.write_text("- name: x\n  type: A\n  changetype: add\n")  # no ttl
    _, sink = _warn_sink()
    with pytest.raises(ValidationError):
        from_file(src, zone="example.com", verbose=0, warn=sink)


def test_from_file_unknown_field_rejected(tmp_path: Path) -> None:
    # Rc0WriteModel extra="forbid" must survive through the parser.
    src = tmp_path / "typo.yaml"
    src.write_text(
        "- name: www.example.com.\n  type: A\n  ttl: 3600\n"
        "  changetype: add\n  records: []\n  note: typo\n",
    )
    _, sink = _warn_sink()
    with pytest.raises(ValidationError):
        from_file(src, zone="example.com", verbose=0, warn=sink)
```

- [ ] **Step 4.2 — Run the test to verify it fails**

Run: `uv run pytest tests/unit/test_rrset_parse_file.py -v --no-cov`
Expected: FAIL with `ImportError: cannot import name 'from_file'`.

- [ ] **Step 4.3 — Extend `rrsets/parse.py`**

Append to `src/rc0/rrsets/parse.py` (keep the existing `from_flags` function):

```python
# --- imports to add at the top of the file, alongside existing ones ---
import json
from pathlib import Path  # noqa: TC003

import yaml
from pydantic import ValidationError as PydanticValidationError

# --- body to append ---


_SUPPORTED_SUFFIXES: frozenset[str] = frozenset({".json", ".yaml", ".yml"})


def _load_list_of_dicts(path: Path) -> list[dict[str, object]]:
    suffix = path.suffix.lower()
    if suffix not in _SUPPORTED_SUFFIXES:
        raise ValidationError(
            f"Unsupported file extension {suffix!r} for --from-file.",
            hint="Use .json, .yaml, or .yml.",
        )
    raw_text = path.read_text(encoding="utf-8")
    parsed: object
    if suffix == ".json":
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise ValidationError(
                f"Invalid JSON in {path}: {exc.msg} (line {exc.lineno}).",
                hint="Check for trailing commas or mismatched brackets.",
            ) from exc
    else:
        try:
            parsed = yaml.safe_load(raw_text)
        except yaml.YAMLError as exc:
            raise ValidationError(
                f"Invalid YAML in {path}: {exc}.",
                hint="Run a YAML linter on the file.",
            ) from exc
    if not isinstance(parsed, list):
        raise ValidationError(
            f"{path} must be a list of rrset change objects, got "
            f"{type(parsed).__name__}.",
            hint="See `rc0 help rrset-format` for the expected shape.",
        )
    rows: list[dict[str, object]] = []
    for i, item in enumerate(parsed):
        if not isinstance(item, dict):
            raise ValidationError(
                f"Item {i} in {path} must be an object, got {type(item).__name__}.",
            )
        rows.append(item)
    return rows


def from_file(
    path: Path,
    *,
    zone: str,
    verbose: int,
    warn: Callable[[str], None],
) -> list[RRsetChange]:
    """Parse a JSON/YAML file into a list of :class:`RRsetChange`.

    File shape (one list item per rrset, mirrors the API PATCH body):

    .. code-block:: yaml

       - name: www.example.com.
         type: A
         ttl: 3600
         changetype: add
         records:
           - content: 10.0.0.1
    """
    rows = _load_list_of_dicts(path)
    changes: list[RRsetChange] = []
    for i, row in enumerate(rows):
        raw_name = row.get("name")
        if not isinstance(raw_name, str):
            raise ValidationError(
                f"Item {i} in {path} is missing a string `name`.",
            )
        qualified, rewritten = qualify_name(raw_name, zone=zone)
        _maybe_warn(
            raw=raw_name, qualified=qualified, rewritten=rewritten,
            verbose=verbose, warn=warn,
        )
        try:
            change = RRsetChange.model_validate({**row, "name": qualified})
        except PydanticValidationError as exc:
            raise ValidationError(
                f"Item {i} in {path} failed validation: "
                + "; ".join(
                    f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
                    for e in exc.errors()
                ),
                hint="See `rc0 help rrset-format` for the expected shape.",
            ) from exc
        changes.append(change)
    return changes
```

- [ ] **Step 4.4 — Run the test to verify it passes**

Run: `uv run pytest tests/unit/test_rrset_parse_file.py -v --no-cov`
Expected: PASS (7 tests).

- [ ] **Step 4.5 — Commit**

```bash
git add src/rc0/rrsets/parse.py tests/unit/test_rrset_parse_file.py
git commit -m "feat(rrsets): JSON/YAML --from-file parser"
```

---

## Task 5 — BIND zone-file parser (`--zone-file`)

**Files:**
- Modify: `src/rc0/rrsets/parse.py` (add `from_zonefile`)
- Test: `tests/unit/test_rrset_parse_zonefile.py`

- [ ] **Step 5.1 — Write the failing test**

```python
# tests/unit/test_rrset_parse_zonefile.py
"""Tests for rc0.rrsets.parse.from_zonefile (BIND)."""

from __future__ import annotations

from pathlib import Path

import pytest

from rc0.client.errors import ValidationError
from rc0.rrsets.parse import from_zonefile


def test_from_zonefile_basic(tmp_path: Path) -> None:
    zf = tmp_path / "example.com.zone"
    zf.write_text(
        "$ORIGIN example.com.\n"
        "$TTL 3600\n"
        "@     IN SOA ns1.example.com. admin.example.com. 1 7200 3600 1209600 3600\n"
        "@     IN NS  ns1.example.com.\n"
        "@     IN NS  ns2.example.com.\n"
        "www   IN A   10.0.0.1\n"
        "www   IN A   10.0.0.2\n"
        "mail  IN MX  10 mx.example.com.\n",
    )
    rrsets = from_zonefile(zf, zone="example.com")
    by_name_type = {(r.name, r.type): r for r in rrsets}
    assert ("example.com.", "SOA") in by_name_type
    ns = by_name_type[("example.com.", "NS")]
    assert {r.content for r in ns.records} == {
        "ns1.example.com.", "ns2.example.com.",
    }
    www_a = by_name_type[("www.example.com.", "A")]
    assert {r.content for r in www_a.records} == {"10.0.0.1", "10.0.0.2"}
    assert www_a.ttl == 3600
    mx = by_name_type[("mail.example.com.", "MX")]
    assert mx.records[0].content == "10 mx.example.com."


def test_from_zonefile_invalid_rejected(tmp_path: Path) -> None:
    zf = tmp_path / "broken.zone"
    zf.write_text("this is not a zone file, just prose.\n")
    with pytest.raises(ValidationError) as exc:
        from_zonefile(zf, zone="example.com")
    assert "parse" in exc.value.message.lower() or "zone" in exc.value.message.lower()


def test_from_zonefile_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        from_zonefile(tmp_path / "nope.zone", zone="example.com")
```

- [ ] **Step 5.2 — Run the test to verify it fails**

Run: `uv run pytest tests/unit/test_rrset_parse_zonefile.py -v --no-cov`
Expected: FAIL with `ImportError: cannot import name 'from_zonefile'`.

- [ ] **Step 5.3 — Add `from_zonefile` to `rrsets/parse.py`**

Append to `src/rc0/rrsets/parse.py`:

```python
# --- add to imports ---
import dns.exception
import dns.name
import dns.rdataclass
import dns.rdataset
import dns.rdatatype
import dns.zone

from rc0.models.rrset_write import RRsetInput

# --- append to module body ---


def from_zonefile(path: Path, *, zone: str) -> list[RRsetInput]:
    """Parse a BIND zone file into a list of :class:`RRsetInput` (PUT body rows).

    Rendered via ``dnspython``; the caller feeds the result into
    ``rc0 record replace-all``. ``$ORIGIN`` is forced to ``zone`` so a zone
    file that already declares a different origin gets rewritten to the
    command's target.
    """
    if not path.exists():
        raise ValidationError(
            f"Zone file {path} does not exist.",
            hint="Double-check the --zone-file path.",
        )
    origin = dns.name.from_text(zone.rstrip(".") + ".")
    try:
        z = dns.zone.from_file(str(path), origin=origin, relativize=False)
    except (dns.exception.DNSException, OSError) as exc:
        raise ValidationError(
            f"Failed to parse zone file {path}: {exc}.",
            hint="Ensure the file is RFC 1035 zone-file syntax; check $ORIGIN "
                 "and $TTL directives.",
        ) from exc
    rrsets: list[RRsetInput] = []
    for name, node in z.nodes.items():
        for rds in node.rdatasets:
            if rds.rdclass != dns.rdataclass.IN:
                continue
            rrsets.append(
                RRsetInput(
                    name=name.to_text(),
                    type=dns.rdatatype.to_text(rds.rdtype),
                    ttl=rds.ttl,
                    records=[
                        RecordInput(content=rd.to_text())
                        for rd in rds
                    ],
                ),
            )
    rrsets.sort(key=lambda r: (r.name, r.type))
    return rrsets
```

- [ ] **Step 5.4 — Run the test to verify it passes**

Run: `uv run pytest tests/unit/test_rrset_parse_zonefile.py -v --no-cov`
Expected: PASS (3 tests).

- [ ] **Step 5.5 — Commit**

```bash
git add src/rc0/rrsets/parse.py tests/unit/test_rrset_parse_zonefile.py
git commit -m "feat(rrsets): BIND --zone-file parser"
```

---

## Task 6 — API wrappers for /rrsets mutations

**Files:**
- Create: `src/rc0/api/rrsets_write.py`
- Test: `tests/unit/test_rrsets_write_api.py`

- [ ] **Step 6.1 — Write the failing test**

```python
# tests/unit/test_rrsets_write_api.py
"""API wrapper tests for PATCH/PUT/DELETE on /api/v2/zones/{zone}/rrsets."""

from __future__ import annotations

import json

import httpx
import respx

from rc0.api import rrsets_write as api
from rc0.client.dry_run import DryRunResult
from rc0.client.http import Client
from rc0.models.rrset_write import (
    RecordInput,
    RRsetChange,
    RRsetInput,
)


def _client() -> Client:
    return Client(api_url="https://my.rcodezero.at", token="tk")


@respx.mock
def test_patch_rrsets_live() -> None:
    route = respx.patch(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    change = RRsetChange(
        name="www.example.com.", type="A", ttl=3600, changetype="add",
        records=[RecordInput(content="10.0.0.1")],
    )
    with _client() as client:
        result = api.patch_rrsets(
            client, zone="example.com", changes=[change],
            dry_run=False, summary="…",
        )
    assert route.called
    sent = json.loads(route.calls.last.request.content)
    assert sent == [
        {
            "name": "www.example.com.", "type": "A", "ttl": 3600,
            "changetype": "add",
            "records": [{"content": "10.0.0.1", "disabled": False}],
        },
    ]
    assert result == {"status": "ok"}


def test_patch_rrsets_dry_run() -> None:
    change = RRsetChange(
        name="www.example.com.", type="A", ttl=3600, changetype="add",
        records=[RecordInput(content="10.0.0.1")],
    )
    with _client() as client:
        result = api.patch_rrsets(
            client, zone="example.com", changes=[change],
            dry_run=True, summary="Would add 1 rrset to example.com.",
        )
    assert isinstance(result, DryRunResult)
    assert result.request.method == "PATCH"
    assert result.request.url.endswith("/api/v2/zones/example.com/rrsets")
    assert result.request.body == [
        {
            "name": "www.example.com.", "type": "A", "ttl": 3600,
            "changetype": "add",
            "records": [{"content": "10.0.0.1", "disabled": False}],
        },
    ]
    assert "example.com" in result.summary


@respx.mock
def test_put_rrsets_live_wraps_in_rrsets_key() -> None:
    route = respx.put(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    rrset = RRsetInput(
        name="www.example.com.", type="A", ttl=3600,
        records=[RecordInput(content="10.0.0.1")],
    )
    with _client() as client:
        api.put_rrsets(
            client, zone="example.com", rrsets=[rrset],
            dry_run=False, summary="…",
        )
    sent = json.loads(route.calls.last.request.content)
    assert sent == {
        "rrsets": [
            {
                "name": "www.example.com.", "type": "A", "ttl": 3600,
                "records": [{"content": "10.0.0.1", "disabled": False}],
            },
        ],
    }


def test_put_rrsets_dry_run() -> None:
    rrset = RRsetInput(
        name="www.example.com.", type="A", ttl=3600,
        records=[RecordInput(content="10.0.0.1")],
    )
    with _client() as client:
        result = api.put_rrsets(
            client, zone="example.com", rrsets=[rrset],
            dry_run=True, summary="Would replace 1 rrset in example.com.",
        )
    assert isinstance(result, DryRunResult)
    assert result.request.method == "PUT"
    assert result.request.body == {
        "rrsets": [
            {
                "name": "www.example.com.", "type": "A", "ttl": 3600,
                "records": [{"content": "10.0.0.1", "disabled": False}],
            },
        ],
    }


@respx.mock
def test_clear_rrsets_live() -> None:
    route = respx.delete(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(204))
    with _client() as client:
        result = api.clear_rrsets(client, zone="example.com", dry_run=False)
    assert route.called
    assert result == {"status": "ok"}


def test_clear_rrsets_dry_run() -> None:
    with _client() as client:
        result = api.clear_rrsets(client, zone="example.com", dry_run=True)
    assert isinstance(result, DryRunResult)
    assert result.request.method == "DELETE"
    assert result.request.url.endswith("/api/v2/zones/example.com/rrsets")
    assert result.request.body is None
    assert "clear" in result.summary.lower() or "delete" in result.summary.lower()
```

- [ ] **Step 6.2 — Run the test to verify it fails**

Run: `uv run pytest tests/unit/test_rrsets_write_api.py -v --no-cov`
Expected: FAIL with `ModuleNotFoundError: No module named 'rc0.api.rrsets_write'`.

- [ ] **Step 6.3 — Implement the wrappers**

```python
# src/rc0/api/rrsets_write.py
"""Write-endpoint wrappers for /api/v2/zones/{zone}/rrsets.

All three wrappers route through :func:`rc0.client.mutations.execute_mutation`
so the dry-run/live code paths share one dispatcher (and one parity test).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rc0.client.mutations import execute_mutation
from rc0.models.rrset_write import ReplaceRRsetBody, RRsetChange, RRsetInput

if TYPE_CHECKING:
    from rc0.client.dry_run import DryRunResult
    from rc0.client.http import Client


def patch_rrsets(
    client: Client,
    *,
    zone: str,
    changes: list[RRsetChange],
    dry_run: bool,
    summary: str,
    side_effects: list[str] | None = None,
) -> DryRunResult | dict[str, Any]:
    """PATCH /api/v2/zones/{zone}/rrsets with a list-shaped body."""
    body: list[dict[str, Any]] = [c.model_dump() for c in changes]
    return execute_mutation(
        client,
        method="PATCH",
        path=f"/api/v2/zones/{zone}/rrsets",
        body=body,
        dry_run=dry_run,
        summary=summary,
        side_effects=side_effects,
    )


def put_rrsets(
    client: Client,
    *,
    zone: str,
    rrsets: list[RRsetInput],
    dry_run: bool,
    summary: str,
) -> DryRunResult | dict[str, Any]:
    """PUT /api/v2/zones/{zone}/rrsets with the ``{"rrsets":[…]}`` envelope."""
    body = ReplaceRRsetBody(rrsets=rrsets).model_dump()
    return execute_mutation(
        client,
        method="PUT",
        path=f"/api/v2/zones/{zone}/rrsets",
        body=body,
        dry_run=dry_run,
        summary=summary,
        side_effects=["replaces_zone_contents"],
    )


def clear_rrsets(
    client: Client,
    *,
    zone: str,
    dry_run: bool,
) -> DryRunResult | dict[str, Any]:
    """DELETE /api/v2/zones/{zone}/rrsets — wipes every rrset except SOA/NS."""
    return execute_mutation(
        client,
        method="DELETE",
        path=f"/api/v2/zones/{zone}/rrsets",
        dry_run=dry_run,
        summary=f"Would clear all non-apex rrsets from {zone}.",
        side_effects=["deletes_rrsets"],
    )
```

- [ ] **Step 6.4 — Run the test to verify it passes**

Run: `uv run pytest tests/unit/test_rrsets_write_api.py -v --no-cov`
Expected: PASS (6 tests).

- [ ] **Step 6.5 — Commit**

```bash
git add src/rc0/api/rrsets_write.py tests/unit/test_rrsets_write_api.py
git commit -m "feat(api): PATCH/PUT/DELETE wrappers for /rrsets"
```

---

## Task 7 — CLI: `rc0 record add` and `rc0 record update`

The two commands share the same flag surface and both route to
`patch_rrsets` with a single-row body; the only difference is `changetype`.

**Files:**
- Modify: `src/rc0/commands/record.py`
- Create: `tests/integration/test_record_write_commands.py`

- [ ] **Step 7.1 — Write the failing integration tests**

```python
# tests/integration/test_record_write_commands.py
"""Integration tests for Phase 3 `rc0 record` write commands."""

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


# -------- record add --------

@respx.mock
def test_record_add_live(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.patch(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    r = cli.invoke(
        app,
        [
            "--token", "tk", "-o", "json",
            "record", "add", "example.com",
            "--name", "www", "--type", "A", "--ttl", "3600",
            "--content", "10.0.0.1", "--content", "10.0.0.2",
        ],
    )
    assert r.exit_code == 0, r.stdout
    assert route.called
    sent = json.loads(route.calls.last.request.content)
    assert sent == [
        {
            "name": "www.example.com.", "type": "A", "ttl": 3600,
            "changetype": "add",
            "records": [
                {"content": "10.0.0.1", "disabled": False},
                {"content": "10.0.0.2", "disabled": False},
            ],
        },
    ]


def test_record_add_dry_run(cli: CliRunner, isolated_config: Path) -> None:
    r = cli.invoke(
        app,
        [
            "--token", "tk", "-o", "json", "--dry-run",
            "record", "add", "example.com",
            "--name", "www", "--type", "A",
            "--content", "10.0.0.1",
        ],
    )
    assert r.exit_code == 0, r.stdout
    parsed = json.loads(r.stdout)
    assert parsed["dry_run"] is True
    assert parsed["request"]["method"] == "PATCH"
    assert parsed["request"]["body"][0]["changetype"] == "add"


def test_record_add_ttl_below_floor_exits_7(
    cli: CliRunner, isolated_config: Path,
) -> None:
    r = cli.invoke(
        app,
        [
            "--token", "tk",
            "record", "add", "example.com",
            "--name", "www", "--type", "A", "--ttl", "30",
            "--content", "10.0.0.1",
        ],
    )
    assert r.exit_code == 7, r.stdout


def test_record_add_bad_ipv4_exits_7(
    cli: CliRunner, isolated_config: Path,
) -> None:
    r = cli.invoke(
        app,
        [
            "--token", "tk",
            "record", "add", "example.com",
            "--name", "www", "--type", "A",
            "--content", "not-an-ip",
        ],
    )
    assert r.exit_code == 7


# -------- record update --------

@respx.mock
def test_record_update_live(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.patch(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    r = cli.invoke(
        app,
        [
            "--token", "tk", "-o", "json",
            "record", "update", "example.com",
            "--name", "www.example.com.", "--type", "A",
            "--content", "10.0.0.9",
        ],
    )
    assert r.exit_code == 0, r.stdout
    sent = json.loads(route.calls.last.request.content)
    assert sent[0]["changetype"] == "update"
    assert sent[0]["records"] == [{"content": "10.0.0.9", "disabled": False}]
```

- [ ] **Step 7.2 — Run the test to verify it fails**

Run: `uv run pytest tests/integration/test_record_write_commands.py -v --no-cov`
Expected: FAIL — `record add` / `record update` do not exist yet.

- [ ] **Step 7.3 — Extend `commands/record.py`**

Add these imports at the top of `src/rc0/commands/record.py` (leave existing
imports untouched):

```python
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path  # noqa: TC003

from rc0.api import rrsets_write as rrsets_write_api
from rc0.client.dry_run import DryRunResult
from rc0.confirm import confirm_typed, confirm_yes_no
from rc0.rrsets import parse as rrsets_parse
from rc0.validation import rrsets as rrsets_validate
```

Then append the following to the bottom of `src/rc0/commands/record.py`:

```python
# ---------------------------------------------------------- Phase 3 mutations


class RecordType(StrEnum):
    """A permissive enum — Typer only uses it for case-insensitive parsing.

    We don't fence on type here: the API validates the RR type, and adding a
    whitelist would block valid new types (SVCB, HTTPS, …) the moment they ship.
    """

    A = "A"
    AAAA = "AAAA"
    CNAME = "CNAME"
    MX = "MX"
    TXT = "TXT"
    NS = "NS"
    SRV = "SRV"
    CAA = "CAA"
    PTR = "PTR"
    SOA = "SOA"


NameOpt = Annotated[
    str,
    typer.Option(
        "--name", help="Record name. Relative to the zone or absolute (with trailing dot).",
    ),
]
TypeOpt = Annotated[
    str,
    typer.Option(
        "--type", help="RR type, e.g. A, AAAA, MX, CNAME, TXT. Case-insensitive.",
    ),
]
TtlOpt = Annotated[
    int,
    typer.Option("--ttl", min=1, help="TTL in seconds (must be ≥ 60, the provider floor)."),
]
ContentOpt = Annotated[
    list[str] | None,
    typer.Option(
        "--content",
        help="Record content. Repeat to aggregate into one RRset (A/AAAA/TXT/…); "
             "for MX, use `--content '10 mail.example.com.'`.",
    ),
]
DisabledOpt = Annotated[
    bool,
    typer.Option(
        "--disabled/--enabled",
        help="Store but hide the record (API disabled=true). Default: enabled.",
    ),
]
FromFileOpt = Annotated[
    Path | None,
    typer.Option(
        "--from-file",
        help="Path to a JSON/YAML file mirroring the PATCH body (list of rrset changes).",
        exists=False,  # we raise our own ValidationError to stay on exit 7
    ),
]
ZoneFileOpt = Annotated[
    Path | None,
    typer.Option(
        "--zone-file",
        help="Path to a BIND zone file (only for `record replace-all`).",
    ),
]


def _render_mutation(
    result: DryRunResult | dict[str, object], state: AppState,
) -> None:
    payload = result.to_dict() if isinstance(result, DryRunResult) else result
    typer.echo(render(payload, fmt=state.effective_output))


def _warn(state: AppState) -> Callable[[str], None]:
    """Build a stderr warner bound to this invocation's verbosity."""
    def _emit(line: str) -> None:
        if state.verbose >= 1:
            typer.secho(line, err=True)
    return _emit


@app.command("add")
def add_cmd(
    ctx: typer.Context,
    zone: ZoneArg,
    name: NameOpt,
    type_: TypeOpt,
    contents: ContentOpt = None,
    ttl: TtlOpt = 3600,
    disabled: DisabledOpt = False,
) -> None:
    """Add a single RRset. API: PATCH /api/v2/zones/{zone}/rrsets"""
    state: AppState = ctx.obj
    change = rrsets_parse.from_flags(
        name=name, type_=type_, ttl=ttl,
        contents=list(contents or []),
        disabled=disabled, changetype="add",
        zone=zone, verbose=state.verbose,
        warn=_warn(state),
    )
    rrsets_validate.validate_changes([change])
    with _client(state) as client:
        result = rrsets_write_api.patch_rrsets(
            client, zone=zone, changes=[change],
            dry_run=state.dry_run,
            summary=f"Would add {change.type} rrset {change.name} "
                    f"({len(change.records)} record(s)).",
            side_effects=["creates_rrset"],
        )
    _render_mutation(result, state)


@app.command("update")
def update_cmd(
    ctx: typer.Context,
    zone: ZoneArg,
    name: NameOpt,
    type_: TypeOpt,
    contents: ContentOpt = None,
    ttl: TtlOpt = 3600,
    disabled: DisabledOpt = False,
) -> None:
    """Replace an RRset's records. API: PATCH /api/v2/zones/{zone}/rrsets"""
    state: AppState = ctx.obj
    change = rrsets_parse.from_flags(
        name=name, type_=type_, ttl=ttl,
        contents=list(contents or []),
        disabled=disabled, changetype="update",
        zone=zone, verbose=state.verbose,
        warn=_warn(state),
    )
    rrsets_validate.validate_changes([change])
    with _client(state) as client:
        result = rrsets_write_api.patch_rrsets(
            client, zone=zone, changes=[change],
            dry_run=state.dry_run,
            summary=f"Would replace records on {change.type} rrset {change.name} "
                    f"(to {len(change.records)} record(s)).",
            side_effects=["updates_rrset"],
        )
    _render_mutation(result, state)
```

- [ ] **Step 7.4 — Run the tests to verify they pass**

Run: `uv run pytest tests/integration/test_record_write_commands.py::test_record_add_live tests/integration/test_record_write_commands.py::test_record_add_dry_run tests/integration/test_record_write_commands.py::test_record_add_ttl_below_floor_exits_7 tests/integration/test_record_write_commands.py::test_record_add_bad_ipv4_exits_7 tests/integration/test_record_write_commands.py::test_record_update_live -v --no-cov`
Expected: PASS (5 tests).

- [ ] **Step 7.5 — Commit**

```bash
git add src/rc0/commands/record.py tests/integration/test_record_write_commands.py
git commit -m "feat(cli): record add / record update"
```

---

## Task 8 — CLI: `rc0 record delete` (y/N confirmation)

**Files:**
- Modify: `src/rc0/commands/record.py`
- Modify: `tests/integration/test_record_write_commands.py` (append)

- [ ] **Step 8.1 — Append the failing tests**

Append to `tests/integration/test_record_write_commands.py`:

```python
# -------- record delete --------


@respx.mock
def test_record_delete_y_proceeds(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.patch(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    r = cli.invoke(
        app,
        [
            "--token", "tk", "-o", "json",
            "record", "delete", "example.com",
            "--name", "www", "--type", "A",
        ],
        input="y\n",
    )
    assert r.exit_code == 0, r.stdout
    sent = json.loads(route.calls.last.request.content)
    assert sent[0]["changetype"] == "delete"
    assert sent[0]["records"] == []


@respx.mock
def test_record_delete_declined_exits_12(
    cli: CliRunner, isolated_config: Path,
) -> None:
    route = respx.patch(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    r = cli.invoke(
        app,
        [
            "--token", "tk",
            "record", "delete", "example.com",
            "--name", "www", "--type", "A",
        ],
        input="n\n",
    )
    assert r.exit_code == 12
    assert not route.called


@respx.mock
def test_record_delete_yes_skips_prompt(
    cli: CliRunner, isolated_config: Path,
) -> None:
    route = respx.patch(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    r = cli.invoke(
        app,
        [
            "--token", "tk", "-y", "-o", "json",
            "record", "delete", "example.com",
            "--name", "www", "--type", "A",
        ],
    )
    assert r.exit_code == 0, r.stdout
    assert route.called


def test_record_delete_dry_run_skips_prompt_and_network(
    cli: CliRunner, isolated_config: Path,
) -> None:
    r = cli.invoke(
        app,
        [
            "--token", "tk", "-o", "json", "--dry-run",
            "record", "delete", "example.com",
            "--name", "www", "--type", "A",
        ],
    )
    assert r.exit_code == 0, r.stdout
    parsed = json.loads(r.stdout)
    assert parsed["dry_run"] is True
    assert parsed["request"]["body"][0]["changetype"] == "delete"
```

- [ ] **Step 8.2 — Run to verify failure**

Run: `uv run pytest tests/integration/test_record_write_commands.py -k delete -v --no-cov`
Expected: FAIL — `record delete` does not exist yet.

- [ ] **Step 8.3 — Add `delete_cmd` to `commands/record.py`**

Append to `src/rc0/commands/record.py` (after `update_cmd`):

```python
@app.command("delete")
def delete_cmd(
    ctx: typer.Context,
    zone: ZoneArg,
    name: NameOpt,
    type_: TypeOpt,
    ttl: TtlOpt = 3600,
) -> None:
    """Delete an RRset. API: PATCH /api/v2/zones/{zone}/rrsets (changetype=delete)

    Per mission-plan §18.4: always prompts for confirmation; pass -y for scripts.
    """
    state: AppState = ctx.obj
    change = rrsets_parse.from_flags(
        name=name, type_=type_, ttl=ttl,
        contents=[], disabled=False, changetype="delete",
        zone=zone, verbose=state.verbose,
        warn=_warn(state),
    )
    rrsets_validate.validate_changes([change])
    if not state.dry_run and not state.yes:
        confirm_yes_no(
            f"Would delete {change.type} rrset {change.name} from zone {zone}.",
        )
    with _client(state) as client:
        result = rrsets_write_api.patch_rrsets(
            client, zone=zone, changes=[change],
            dry_run=state.dry_run,
            summary=f"Would delete {change.type} rrset {change.name}.",
            side_effects=["deletes_rrset"],
        )
    _render_mutation(result, state)
```

- [ ] **Step 8.4 — Run the delete tests to verify they pass**

Run: `uv run pytest tests/integration/test_record_write_commands.py -k delete -v --no-cov`
Expected: PASS (4 tests).

- [ ] **Step 8.5 — Commit**

```bash
git add src/rc0/commands/record.py tests/integration/test_record_write_commands.py
git commit -m "feat(cli): record delete with y/N confirmation"
```

---

## Task 9 — CLI: `rc0 record apply` (`--from-file`, typed-zone confirmation)

**Files:**
- Modify: `src/rc0/commands/record.py`
- Modify: `tests/integration/test_record_write_commands.py` (append)

- [ ] **Step 9.1 — Append the failing tests**

Append to `tests/integration/test_record_write_commands.py`:

```python
# -------- record apply --------


def _write_changes_yaml(path: Path) -> None:
    path.write_text(
        """- name: api.example.com.
  type: A
  ttl: 3600
  changetype: add
  records:
    - content: 10.0.0.5
- name: old.example.com.
  type: A
  ttl: 3600
  changetype: delete
""",
    )


@respx.mock
def test_record_apply_typed_confirmation_proceeds(
    cli: CliRunner, isolated_config: Path, tmp_path: Path,
) -> None:
    changes = tmp_path / "changes.yaml"
    _write_changes_yaml(changes)
    route = respx.patch(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    r = cli.invoke(
        app,
        [
            "--token", "tk", "-o", "json",
            "record", "apply", "example.com",
            "--from-file", str(changes),
        ],
        input="example.com\n",
    )
    assert r.exit_code == 0, r.stdout
    sent = json.loads(route.calls.last.request.content)
    assert len(sent) == 2
    assert {c["changetype"] for c in sent} == {"add", "delete"}


@respx.mock
def test_record_apply_wrong_confirmation_exits_12(
    cli: CliRunner, isolated_config: Path, tmp_path: Path,
) -> None:
    changes = tmp_path / "changes.yaml"
    _write_changes_yaml(changes)
    route = respx.patch(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    r = cli.invoke(
        app,
        [
            "--token", "tk",
            "record", "apply", "example.com",
            "--from-file", str(changes),
        ],
        input="not-the-zone\n",
    )
    assert r.exit_code == 12
    assert not route.called


def test_record_apply_requires_from_file(
    cli: CliRunner, isolated_config: Path,
) -> None:
    r = cli.invoke(
        app,
        ["--token", "tk", "record", "apply", "example.com"],
    )
    assert r.exit_code == 7


def test_record_apply_dry_run(
    cli: CliRunner, isolated_config: Path, tmp_path: Path,
) -> None:
    changes = tmp_path / "changes.yaml"
    _write_changes_yaml(changes)
    r = cli.invoke(
        app,
        [
            "--token", "tk", "-o", "json", "--dry-run",
            "record", "apply", "example.com",
            "--from-file", str(changes),
        ],
    )
    assert r.exit_code == 0, r.stdout
    parsed = json.loads(r.stdout)
    assert parsed["dry_run"] is True
    assert parsed["request"]["method"] == "PATCH"
    assert len(parsed["request"]["body"]) == 2
```

- [ ] **Step 9.2 — Run to verify failure**

Run: `uv run pytest tests/integration/test_record_write_commands.py -k apply -v --no-cov`
Expected: FAIL — `record apply` does not exist.

- [ ] **Step 9.3 — Add `apply_cmd` to `commands/record.py`**

Append:

```python
@app.command("apply")
def apply_cmd(
    ctx: typer.Context,
    zone: ZoneArg,
    from_file: FromFileOpt = None,
) -> None:
    """Apply a batch of rrset changes from a JSON/YAML file.

    API: PATCH /api/v2/zones/{zone}/rrsets

    The file format mirrors the API PATCH body exactly (a list of rrset change
    objects, each with ``changetype`` set to ``add``, ``update`` or ``delete``).
    See `rc0 help rrset-format` for the full schema.
    """
    state: AppState = ctx.obj
    if from_file is None:
        raise ValidationError(
            "`record apply` requires --from-file.",
            hint="Pass a JSON/YAML file with the rrset changes; see `rc0 help rrset-format`.",
        )
    changes = rrsets_parse.from_file(
        from_file, zone=zone, verbose=state.verbose,
        warn=_warn(state),
    )
    rrsets_validate.validate_changes(changes)
    if not state.dry_run and not state.yes:
        confirm_typed(
            zone,
            summary=(
                f"Would apply {len(changes)} rrset change(s) to {zone} "
                "(mixed add/update/delete)."
            ),
        )
    with _client(state) as client:
        result = rrsets_write_api.patch_rrsets(
            client, zone=zone, changes=changes,
            dry_run=state.dry_run,
            summary=f"Would apply {len(changes)} rrset change(s) to {zone}.",
            side_effects=["applies_rrset_batch"],
        )
    _render_mutation(result, state)
```

- [ ] **Step 9.4 — Run the apply tests to verify they pass**

Run: `uv run pytest tests/integration/test_record_write_commands.py -k apply -v --no-cov`
Expected: PASS (4 tests).

- [ ] **Step 9.5 — Commit**

```bash
git add src/rc0/commands/record.py tests/integration/test_record_write_commands.py
git commit -m "feat(cli): record apply --from-file with typed-zone confirmation"
```

---

## Task 10 — CLI: `rc0 record replace-all` (`--from-file` or `--zone-file`)

**Files:**
- Modify: `src/rc0/commands/record.py`
- Modify: `tests/integration/test_record_write_commands.py` (append)

- [ ] **Step 10.1 — Append the failing tests**

Append to `tests/integration/test_record_write_commands.py`:

```python
# -------- record replace-all --------


def _write_replacement_yaml(path: Path) -> None:
    # A full replacement file has NO `changetype` — every row is the desired
    # final state of the RRset at that (name, type).
    path.write_text(
        """- name: example.com.
  type: SOA
  ttl: 3600
  records:
    - content: ns1.example.com. admin.example.com. 1 7200 3600 1209600 3600
- name: www.example.com.
  type: A
  ttl: 3600
  records:
    - content: 10.0.0.1
""",
    )


def _write_zone_file(path: Path) -> None:
    path.write_text(
        "$ORIGIN example.com.\n"
        "$TTL 3600\n"
        "@     IN SOA ns1.example.com. admin.example.com. 1 7200 3600 1209600 3600\n"
        "@     IN NS  ns1.example.com.\n"
        "www   IN A   10.0.0.1\n",
    )


@respx.mock
def test_record_replace_all_from_file(
    cli: CliRunner, isolated_config: Path, tmp_path: Path,
) -> None:
    src = tmp_path / "rep.yaml"
    _write_replacement_yaml(src)
    route = respx.put(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    r = cli.invoke(
        app,
        [
            "--token", "tk", "-o", "json",
            "record", "replace-all", "example.com",
            "--from-file", str(src),
        ],
        input="example.com\n",
    )
    assert r.exit_code == 0, r.stdout
    sent = json.loads(route.calls.last.request.content)
    assert "rrsets" in sent
    assert {r["type"] for r in sent["rrsets"]} == {"SOA", "A"}


@respx.mock
def test_record_replace_all_from_zonefile(
    cli: CliRunner, isolated_config: Path, tmp_path: Path,
) -> None:
    src = tmp_path / "example.com.zone"
    _write_zone_file(src)
    route = respx.put(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    r = cli.invoke(
        app,
        [
            "--token", "tk", "-y", "-o", "json",
            "record", "replace-all", "example.com",
            "--zone-file", str(src),
        ],
    )
    assert r.exit_code == 0, r.stdout
    sent = json.loads(route.calls.last.request.content)
    assert "rrsets" in sent
    types = {r["type"] for r in sent["rrsets"]}
    assert "SOA" in types and "NS" in types and "A" in types


def test_record_replace_all_requires_one_source(
    cli: CliRunner, isolated_config: Path,
) -> None:
    r = cli.invoke(
        app,
        ["--token", "tk", "record", "replace-all", "example.com"],
    )
    assert r.exit_code == 7


def test_record_replace_all_rejects_both_sources(
    cli: CliRunner, isolated_config: Path, tmp_path: Path,
) -> None:
    yaml_src = tmp_path / "a.yaml"
    yaml_src.write_text("[]")
    zf = tmp_path / "a.zone"
    zf.write_text("$ORIGIN example.com.\n@ 3600 IN SOA ns1.example.com. admin.example.com. 1 60 60 60 60\n")
    r = cli.invoke(
        app,
        [
            "--token", "tk",
            "record", "replace-all", "example.com",
            "--from-file", str(yaml_src),
            "--zone-file", str(zf),
        ],
    )
    assert r.exit_code == 7
```

- [ ] **Step 10.2 — Run to verify failure**

Run: `uv run pytest tests/integration/test_record_write_commands.py -k replace_all -v --no-cov`
Expected: FAIL — command does not exist.

- [ ] **Step 10.3 — Add `replace_all_cmd` to `commands/record.py`**

Append:

```python
@app.command("replace-all")
def replace_all_cmd(
    ctx: typer.Context,
    zone: ZoneArg,
    from_file: FromFileOpt = None,
    zone_file: ZoneFileOpt = None,
) -> None:
    """Full zone replacement (zone-transfer semantics).

    API: PUT /api/v2/zones/{zone}/rrsets

    Accepts exactly one of:
      --from-file  JSON/YAML file of rrsets (no `changetype` — each row is the
                   desired final state at that name/type).
      --zone-file  BIND zone file; parsed via dnspython.

    Replaces every rrset in the zone. This is destructive: anything not in the
    input disappears. Prompts for typed-zone confirmation by default.
    """
    state: AppState = ctx.obj
    if (from_file is None) == (zone_file is None):
        raise ValidationError(
            "`record replace-all` needs exactly one of --from-file or --zone-file.",
            hint="JSON/YAML for API-shape input; BIND for zone-file input.",
        )
    if from_file is not None:
        # The PATCH-shape file parser would fail on rows without changetype; we
        # need the PUT shape. Load rows directly and build RRsetInput.
        rrsets = _load_rrsets_from_file(
            from_file, zone=zone, verbose=state.verbose,
            warn=_warn(state),
        )
    else:
        assert zone_file is not None  # noqa: S101
        rrsets = rrsets_parse.from_zonefile(zone_file, zone=zone)
    rrsets_validate.validate_replacement(rrsets)
    if not state.dry_run and not state.yes:
        confirm_typed(
            zone,
            summary=(
                f"Would REPLACE every rrset in {zone} with {len(rrsets)} rrset(s). "
                "This discards anything not in the input."
            ),
        )
    with _client(state) as client:
        result = rrsets_write_api.put_rrsets(
            client, zone=zone, rrsets=rrsets,
            dry_run=state.dry_run,
            summary=f"Would replace every rrset in {zone} with {len(rrsets)} rrset(s).",
        )
    _render_mutation(result, state)
```

Immediately below `replace_all_cmd`, add the small helper (kept inline rather
than exported — `replace-all` is the only caller):

```python
def _load_rrsets_from_file(
    path: Path, *, zone: str, verbose: int, warn: Callable[[str], None],
) -> list["RRsetInput"]:
    """Load a JSON/YAML file as RRsetInput[] (PUT body, no `changetype`)."""
    import json as _json

    import yaml as _yaml
    from pydantic import ValidationError as _PydanticValidationError

    from rc0.models.rrset_write import RRsetInput

    suffix = path.suffix.lower()
    if suffix not in {".json", ".yaml", ".yml"}:
        raise ValidationError(
            f"Unsupported --from-file extension {suffix!r}.",
            hint="Use .json, .yaml, or .yml.",
        )
    text = path.read_text(encoding="utf-8")
    raw = _json.loads(text) if suffix == ".json" else _yaml.safe_load(text)
    if not isinstance(raw, list):
        raise ValidationError(
            f"{path} must be a list of rrset objects.",
            hint="See `rc0 help rrset-format`.",
        )
    out: list[RRsetInput] = []
    for i, row in enumerate(raw):
        if not isinstance(row, dict):
            raise ValidationError(
                f"Item {i} in {path} must be an object.",
            )
        raw_name = row.get("name", "")
        if not isinstance(raw_name, str):
            raise ValidationError(f"Item {i} in {path} has no string `name`.")
        qualified, rewritten = rrsets_validate.qualify_name(raw_name, zone=zone)
        if rewritten and verbose >= 1:
            warn(f"auto-qualified name {raw_name!r} → {qualified!r}")
        try:
            out.append(RRsetInput.model_validate({**row, "name": qualified}))
        except _PydanticValidationError as exc:
            raise ValidationError(
                f"Item {i} in {path} failed validation: "
                + "; ".join(
                    f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
                    for e in exc.errors()
                ),
                hint="`record replace-all --from-file` expects rows without "
                     "`changetype` — each row is the desired final state.",
            ) from exc
    return out
```

Also add `RRsetInput` to the `TYPE_CHECKING` import block near the top of the
file if you wired module-level imports that way — or, simpler, rely on the
inline `from rc0.models.rrset_write import RRsetInput` inside the helper to
avoid polluting the top-level namespace of `commands/record.py`.

- [ ] **Step 10.4 — Run the replace-all tests**

Run: `uv run pytest tests/integration/test_record_write_commands.py -k replace_all -v --no-cov`
Expected: PASS (4 tests).

- [ ] **Step 10.5 — Commit**

```bash
git add src/rc0/commands/record.py tests/integration/test_record_write_commands.py
git commit -m "feat(cli): record replace-all with --from-file / --zone-file"
```

---

## Task 11 — CLI: `rc0 record clear` (typed-zone confirmation)

**Files:**
- Modify: `src/rc0/commands/record.py`
- Modify: `tests/integration/test_record_write_commands.py` (append)

- [ ] **Step 11.1 — Append the failing tests**

Append:

```python
# -------- record clear --------


@respx.mock
def test_record_clear_typed_confirmation_proceeds(
    cli: CliRunner, isolated_config: Path,
) -> None:
    route = respx.delete(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(204))
    r = cli.invoke(
        app,
        [
            "--token", "tk", "-o", "json",
            "record", "clear", "example.com",
        ],
        input="example.com\n",
    )
    assert r.exit_code == 0, r.stdout
    assert route.called


@respx.mock
def test_record_clear_wrong_confirmation_exits_12(
    cli: CliRunner, isolated_config: Path,
) -> None:
    route = respx.delete(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(204))
    r = cli.invoke(
        app,
        [
            "--token", "tk",
            "record", "clear", "example.com",
        ],
        input="nope\n",
    )
    assert r.exit_code == 12
    assert not route.called


def test_record_clear_dry_run(cli: CliRunner, isolated_config: Path) -> None:
    r = cli.invoke(
        app,
        [
            "--token", "tk", "-o", "json", "--dry-run",
            "record", "clear", "example.com",
        ],
    )
    assert r.exit_code == 0, r.stdout
    parsed = json.loads(r.stdout)
    assert parsed["dry_run"] is True
    assert parsed["request"]["method"] == "DELETE"
```

- [ ] **Step 11.2 — Run to verify failure**

Run: `uv run pytest tests/integration/test_record_write_commands.py -k clear -v --no-cov`
Expected: FAIL — command does not exist.

- [ ] **Step 11.3 — Add `clear_cmd`**

Append to `src/rc0/commands/record.py`:

```python
@app.command("clear")
def clear_cmd(ctx: typer.Context, zone: ZoneArg) -> None:
    """Delete every non-apex RRset in a zone.

    API: DELETE /api/v2/zones/{zone}/rrsets

    SOA and NS rrsets at the apex survive; everything else is wiped. Prompts
    for typed-zone confirmation by default.
    """
    state: AppState = ctx.obj
    if not state.dry_run and not state.yes:
        confirm_typed(
            zone,
            summary=f"Would clear every non-apex rrset from {zone}. This cannot be undone.",
        )
    with _client(state) as client:
        result = rrsets_write_api.clear_rrsets(
            client, zone=zone, dry_run=state.dry_run,
        )
    _render_mutation(result, state)
```

- [ ] **Step 11.4 — Run the clear tests**

Run: `uv run pytest tests/integration/test_record_write_commands.py -k clear -v --no-cov`
Expected: PASS (3 tests).

- [ ] **Step 11.5 — Run the whole integration module to sanity-check**

Run: `uv run pytest tests/integration/test_record_write_commands.py -v --no-cov`
Expected: PASS (all 20 tests).

- [ ] **Step 11.6 — Commit**

```bash
git add src/rc0/commands/record.py tests/integration/test_record_write_commands.py
git commit -m "feat(cli): record clear with typed-zone confirmation"
```

---

## Task 12 — Dry-run parity for Phase 3 mutations

**Files:**
- Modify: `tests/unit/test_dry_run_parity.py`

Mission plan §15: every mutation must round-trip byte-identically between
dry-run and mocked live. The Phase 2 parity test is already in place; we extend
its parametrisation.

- [ ] **Step 12.1 — Create a fixture file on disk that both invocations reuse**

Add a `changes_yaml_path` fixture near the top of the file (below the existing
`cli` fixture):

```python
@pytest.fixture
def changes_yaml_path(tmp_path: Path) -> Path:
    """Minimal PATCH-shape changes file; shared between dry-run and live."""
    p = tmp_path / "changes.yaml"
    p.write_text(
        "- name: www.example.com.\n"
        "  type: A\n"
        "  ttl: 3600\n"
        "  changetype: add\n"
        "  records:\n"
        "    - content: 10.0.0.1\n",
    )
    return p
```

- [ ] **Step 12.2 — Extend `PARITY_CASES`**

Append the following entries to `PARITY_CASES` (after the last existing row):

```python
    # --- Phase 3 ---
    (
        "PATCH", "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
        [
            "record", "add", "example.com",
            "--name", "www.example.com.", "--type", "A",
            "--content", "10.0.0.1",
        ],
        200, {"status": "ok"},
    ),
    (
        "PATCH", "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
        [
            "record", "update", "example.com",
            "--name", "www.example.com.", "--type", "A",
            "--content", "10.0.0.2",
        ],
        200, {"status": "ok"},
    ),
    (
        "PATCH", "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
        [
            "-y",
            "record", "delete", "example.com",
            "--name", "www.example.com.", "--type", "A",
        ],
        200, {"status": "ok"},
    ),
    (
        "DELETE", "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
        ["-y", "record", "clear", "example.com"],
        204, None,
    ),
```

- [ ] **Step 12.3 — Add two file-driven parity tests**

`record apply --from-file` and `record replace-all --from-file` can't fit the
single-line `PARITY_CASES` form — they need the `changes_yaml_path` /
`replacement_yaml_path` fixtures. Add them as standalone tests alongside the
parametrised `test_dry_run_parity`:

```python
@pytest.fixture
def replacement_yaml_path(tmp_path: Path) -> Path:
    p = tmp_path / "replacement.yaml"
    p.write_text(
        "- name: www.example.com.\n"
        "  type: A\n"
        "  ttl: 3600\n"
        "  records:\n"
        "    - content: 10.0.0.1\n",
    )
    return p


@respx.mock
def test_dry_run_parity_record_apply(
    cli: CliRunner, isolated_config: Path, changes_yaml_path: Path,
) -> None:
    args = [
        "-y",
        "record", "apply", "example.com",
        "--from-file", str(changes_yaml_path),
    ]
    dry = cli.invoke(app, ["--token", "tk", "-o", "json", "--dry-run", *args])
    assert dry.exit_code == 0, dry.stdout
    dry_req = json.loads(dry.stdout)["request"]

    respx.patch(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    live = cli.invoke(app, ["--token", "tk", "-o", "json", *args])
    assert live.exit_code == 0, live.stdout
    live_req = respx.calls.last.request
    assert dry_req["method"] == "PATCH"
    assert dry_req["url"] == str(live_req.url)
    assert dry_req["body"] == json.loads(live_req.content)


@respx.mock
def test_dry_run_parity_record_replace_all(
    cli: CliRunner, isolated_config: Path, replacement_yaml_path: Path,
) -> None:
    args = [
        "-y",
        "record", "replace-all", "example.com",
        "--from-file", str(replacement_yaml_path),
    ]
    dry = cli.invoke(app, ["--token", "tk", "-o", "json", "--dry-run", *args])
    assert dry.exit_code == 0, dry.stdout
    dry_req = json.loads(dry.stdout)["request"]

    respx.put(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    live = cli.invoke(app, ["--token", "tk", "-o", "json", *args])
    assert live.exit_code == 0, live.stdout
    live_req = respx.calls.last.request
    assert dry_req["method"] == "PUT"
    assert dry_req["url"] == str(live_req.url)
    assert dry_req["body"] == json.loads(live_req.content)
```

- [ ] **Step 12.4 — Run the whole parity suite**

Run: `uv run pytest tests/unit/test_dry_run_parity.py -v --no-cov`
Expected: PASS (20 Phase 2 + 4 new parametrised + 2 standalone = 26 tests).

- [ ] **Step 12.5 — Commit**

```bash
git add tests/unit/test_dry_run_parity.py
git commit -m "test: dry-run parity for Phase 3 rrset mutations"
```

---

## Task 13 — Topic help: `rrset-format.md`

**Files:**
- Create: `src/rc0/topics/rrset-format.md`

- [ ] **Step 13.1 — Write the topic**

```markdown
# rrset-format

`rc0 record` accepts RRset input in three shapes. Pick the one that matches the
task; they cover every non-deprecated v2 endpoint.

## 1. Flag-based (quick, single-rrset)

Best for one-off adds / updates / deletes. Each invocation targets one
`(name, type)` pair. Multiple `--content` flags aggregate into one RRset.

```
rc0 record add example.com \
  --name www --type A --ttl 3600 \
  --content 10.0.0.1 --content 10.0.0.2

rc0 record update example.com \
  --name mail.example.com. --type MX \
  --content "10 mail1.example.com." --content "20 mail2.example.com."

rc0 record delete example.com --name legacy --type A
```

Names may be relative (`www`), absolute with trailing dot (`www.example.com.`),
or `@` for the apex. rc0 auto-qualifies the first two to FQDN + trailing dot,
and warns on stderr when `-v` / `--verbose` is set.

## 2. JSON / YAML batch (`--from-file`)

Best for mixed batches (add + update + delete in one PATCH). Use with
`rc0 record apply <zone> --from-file changes.(json|yaml|yml)`. The file shape
mirrors the PATCH request body exactly: a **list** of rrset change objects.

```yaml
- name: api.example.com.
  type: A
  ttl: 3600
  changetype: add
  records:
    - content: 10.0.0.5
- name: www.example.com.
  type: A
  ttl: 3600
  changetype: update
  records:
    - content: 10.0.0.6
- name: old.example.com.
  type: A
  ttl: 3600
  changetype: delete
```

Required fields per row: `name`, `type`, `ttl`, `changetype`. `records` is
required for `add`/`update`, omitted (or `[]`) for `delete`. Unknown fields
are rejected — typos surface immediately.

`rc0 record replace-all --from-file` uses the **same file layout but without
`changetype`** — every row is the desired final state of the RRset at that
`(name, type)`. Anything not listed is wiped.

## 3. BIND zone file (`--zone-file`)

Only valid with `rc0 record replace-all`. The file is parsed via `dnspython`;
`$ORIGIN` is forced to the CLI's target zone so drift between `$ORIGIN` in the
file and the zone argument can't produce silent cross-zone writes.

```
rc0 record replace-all example.com --zone-file example.com.zone
```

## Validation (client-side, before hitting the API)

| Rule | Mission plan §12 | Behaviour |
|---|---|---|
| Trailing dot on `name` | Auto-fix | Silent unless `-v`; warns to stderr then. |
| RRset size per PATCH | ≤ 1000 | Exit 7 with hint to split or use `replace-all`. |
| RRset size per PUT | ≤ 3000 | Exit 7. |
| CNAME + other type at same label | Reject | Intra-batch only; cross-batch is caught by the API. |
| MX priority | Required | `"10 mail.example.com."` not `"mail.example.com."`. |
| TTL ≥ 60 | Enforced | Provider minimum. |
| A / AAAA content | Real IP | `ipaddress` module validation. |

Failures raise exit code 7 with a `hint`. In `-o json` mode, the error prints
on stderr as the §11 JSON envelope.

## Confirmation

| Command | Prompt |
|---|---|
| `record add` / `record update` | none (additive) |
| `record delete` | simple y/N |
| `record apply` | type the zone name to confirm |
| `record replace-all` | type the zone name to confirm |
| `record clear` | type the zone name to confirm |

`-y` / `--yes` skips any prompt. `--dry-run` skips both the prompt and the
network call. See `rc0 help dry-run`.

## Exporting to any of these shapes

`rc0 record export <zone> -f (bind|json|yaml)` dumps a zone's current rrsets in
any of the formats above. `yaml` and `json` produce replacement-ready files
(no `changetype`); pair with `record replace-all --from-file` to round-trip.
```

- [ ] **Step 13.2 — Verify `rc0 help rrset-format` renders**

Run: `uv run rc0 help rrset-format | head -5`
Expected: first heading line `# rrset-format`.

- [ ] **Step 13.3 — Commit**

```bash
git add src/rc0/topics/rrset-format.md
git commit -m "docs(topics): rrset-format"
```

---

## Task 14 — Full suite + lint + type-check + release prep

**Files:**
- Modify: `src/rc0/__init__.py`, `pyproject.toml`, `CHANGELOG.md`, `CLAUDE.md`

- [ ] **Step 14.1 — Run the whole suite**

Run: `uv run pytest`
Expected: green. Coverage should rise; the Phase 2 floor was 84, actual ≥ 85.7
on macOS/Linux. Phase 3 adds heavy validator/parser code with thorough unit
tests, so coverage should trend up, not down.

- [ ] **Step 14.2 — Lint**

Run:
```
uv run ruff check .
uv run ruff format --check .
```
Expected: clean. If ruff flags the inline imports inside
`_load_rrsets_from_file` (PLC0415 "import outside top-level"), either move
them to the top of the module or add a `# noqa: PLC0415` — the rule is not
currently enabled by the project's ruff config (`E W F I B UP SIM RUF S C4 PIE
PTH TCH`), so this shouldn't fire, but keep an eye on it.

- [ ] **Step 14.3 — Type-check**

Run: `uv run mypy`
Expected: clean.

Known mypy pain points and their resolutions:
- `warn: Callable[[str], None]` vs. `_warn()` returning `object`: add a
  precise return annotation `-> Callable[[str], None]` to `_warn`.
- `from_flags(type_=...)` Literal issues: keep `type_: str` in the CLI
  signature (the API accepts anything, see RecordType docstring) and only
  narrow to Literal at the Pydantic boundary.

- [ ] **Step 14.4 — Bump the version**

Edit `src/rc0/__init__.py`:
```python
__version__ = "0.4.0"
```

Edit `pyproject.toml`:
```toml
version = "0.4.0"
```

- [ ] **Step 14.5 — Consider tightening the coverage floor**

Re-read the coverage total from Step 14.1. If it's ≥ 86%, bump
`fail_under` in `pyproject.toml` accordingly:

```toml
fail_under = 86
```

If the total dropped vs Phase 2 (84%), stop and investigate — Phase 3 is
mostly new, thoroughly-tested code; a regression means we are missing tests,
not that we should lower the floor.

- [ ] **Step 14.6 — Update `CHANGELOG.md`**

Replace the empty `## [Unreleased]` stub with:

```markdown
## [Unreleased]

## [0.4.0] — RRsets

### Added
- `rc0 record add/update/delete` — single-RRset mutations via the PATCH
  endpoint, flag-driven input (`--name`, `--type`, `--ttl`, `--content`).
- `rc0 record apply --from-file FILE.{json,yaml,yml}` — batch PATCH from a
  mixed-changetype file; typed-zone confirmation.
- `rc0 record replace-all --from-file | --zone-file` — full-zone PUT
  replacement; accepts either the API-shape JSON/YAML (no `changetype`) or
  a BIND zone file parsed via `dnspython`. Typed-zone confirmation.
- `rc0 record clear` — DELETE every non-apex RRset in a zone; typed-zone
  confirmation.
- Client-side validation (mission plan §12): trailing-dot auto-fix with a
  stderr warning in `-v` mode, TTL ≥ 60 floor, CNAME-exclusivity check,
  MX priority check, A/AAAA IP sanity, PATCH size ≤ 1000 and PUT size ≤ 3000.
  All surface as exit code 7 with actionable hints.
- Topic help: `rrset-format`.

### Changed
- `rc0.client.mutations.execute_mutation` is now used by the new write
  endpoints — no behavioural change, but it's the shared dispatcher for every
  mutation in the tool now.

### Added (testing)
- Unit tests for every new module (`models.rrset_write`, `validation.rrsets`,
  `rrsets.parse` — flags / file / zone-file each in its own file,
  `api.rrsets_write`).
- Integration tests for each of the six new CLI commands.
- `test_dry_run_parity.py` extended with four parametrised cases plus two
  file-driven cases (`record apply`, `record replace-all --from-file`).
```

Update the footer link table:

```markdown
[Unreleased]: https://github.com/zoltanf/rc0-cli/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/zoltanf/rc0-cli/releases/tag/v0.4.0
[0.3.0]: https://github.com/zoltanf/rc0-cli/releases/tag/v0.3.0
[0.2.0]: https://github.com/zoltanf/rc0-cli/releases/tag/v0.2.0
[0.1.0]: https://github.com/zoltanf/rc0-cli/releases/tag/v0.1.0
```

- [ ] **Step 14.7 — Update `CLAUDE.md`**

Flip the Phase 3 row to **Done** (adjust the date to today's date) and flip
Phase 4 to **Pending — next up**:

```markdown
| 3 RRsets | v0.4.0 | **Done** (YYYY-MM-DD). `rc0 record add/update/delete/apply/replace-all/clear`; flags, JSON/YAML, and BIND zone-file inputs; §12 validation enforced client-side; dry-run parity extended. |
| 4 DNSSEC | v0.5.0 | Pending — next up. |
```

Also update the coverage paragraph if the `fail_under` gate moved in Step
14.5.

- [ ] **Step 14.8 — Re-run the full gate**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy`
Expected: all green.

- [ ] **Step 14.9 — Commit release prep**

```bash
git add src/rc0/__init__.py pyproject.toml CHANGELOG.md CLAUDE.md
git commit -m "chore(release): prep v0.4.0"
```

- [ ] **Step 14.10 — Push branch and open PR**

```bash
git push -u origin phase-3-rrsets
gh pr create --title "Phase 3: RRsets (v0.4.0)" --body "$(cat <<'EOF'
## Summary
- `rc0 record add/update/delete/apply/replace-all/clear` land with flag,
  JSON/YAML, and BIND zone-file inputs (mission plan §5, §12).
- Client-side validation enforces every §12 rule: trailing dots, 1000/PATCH
  and 3000/PUT size limits, CNAME exclusivity, MX priority, TTL ≥ 60,
  A/AAAA IP sanity. Failures → exit 7 with actionable hints.
- Dry-run parity test (`tests/unit/test_dry_run_parity.py`) extended with
  six new cases covering every rrset mutation.

## Test plan
- [x] `uv run pytest` green.
- [x] `uv run ruff check .` clean.
- [x] `uv run ruff format --check .` clean.
- [x] `uv run mypy` clean.
- [x] Manual smoke: `uv run rc0 record add example.com --name www --type A --content 10.0.0.1 --dry-run -o json`
      prints the expected PATCH envelope.
- [x] Manual smoke: `uv run rc0 record apply example.com --from-file changes.yaml`
      prompts `Type "example.com" to confirm:` and exits 12 on mismatch.
- [x] Manual smoke: `uv run rc0 record replace-all example.com --zone-file ./example.com.zone -y`
      sends a PUT with the expected `{"rrsets":[…]}` envelope.
EOF
)"
```

- [ ] **Step 14.11 — After CI passes: merge, tag, push tag**

```bash
gh pr merge --squash --delete-branch
git checkout main && git pull
git tag -a v0.4.0 -m "Phase 3 — RRsets

rc0 record add/update/delete/apply/replace-all/clear. Flag, JSON/YAML, and
BIND zone-file inputs. Client-side validation per mission plan §12.
Dry-run/live parity extended to every rrset mutation."
git push origin v0.4.0
```

Expected: tag visible on GitHub; Phase 3 closed.

---

## Verification summary

After Task 14, every row of mission-plan §14 Phase 3 must be satisfied:

| Check | Source |
|---|---|
| `rc0 record add/update/delete` | Tasks 7 – 8 |
| `rc0 record apply --from-file` | Task 9 |
| `rc0 record replace-all --from-file / --zone-file` | Task 10 |
| `rc0 record clear` | Task 11 |
| Flag-based input | Tasks 3, 7, 8 |
| JSON/YAML file input | Tasks 4, 9, 10 |
| BIND zone-file input | Tasks 5, 10 |
| Trailing-dot auto-fix + warn in verbose | Tasks 2, 3, 4 |
| PATCH/PUT size limits (1000 / 3000) | Task 2 |
| CNAME exclusivity | Task 2 |
| MX priority | Task 2 |
| TTL ≥ 60 | Task 2 |
| A/AAAA IP validation | Task 2 |
| Confirmation semantics (y/N vs typed-zone) | Tasks 8 – 11 |
| `--dry-run` on every mutation | Tasks 6 – 11 |
| Dry-run parity test | Task 12 |
| Topic `rrset-format` | Task 13 |
| CHANGELOG, version, tag | Task 14 |

---

## Out of scope (deferred to later phases)

- `rc0 dnssec sign/unsign/keyrollover/ack-ds/simulate` — Phase 4.
- `rc0 acme *` (ACME challenge add/remove — same `/rrsets` PATCH mechanics
  but against the v1 endpoint with an ACME-permissioned token) — Phase 5.
- Server-side `record diff` against the live zone (preview what
  `replace-all` would actually change) — not in the mission plan; would be
  a Phase 7 ergonomics item.
- Pretty "would apply N changes" per-row summary in `-o table` dry-run
  output for `record apply` / `replace-all` — the JSON/YAML envelope is
  authoritative; a polished human render is a Phase 7 polish item.

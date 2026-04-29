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


# -------- record set --------


@respx.mock
def test_record_set_live(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.patch(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "-o",
            "json",
            "record",
            "set",
            "example.com",
            "--name",
            "www",
            "--type",
            "A",
            "--ttl",
            "3600",
            "--content",
            "10.0.0.1",
            "--content",
            "10.0.0.2",
        ],
    )
    assert r.exit_code == 0, r.stdout
    assert route.called
    sent = json.loads(route.calls.last.request.content)
    assert sent == [
        {
            "name": "www.example.com.",
            "type": "A",
            "ttl": 3600,
            "changetype": "update",
            "records": [
                {"content": "10.0.0.1", "disabled": False},
                {"content": "10.0.0.2", "disabled": False},
            ],
        },
    ]


def test_record_set_dry_run(cli: CliRunner, isolated_config: Path) -> None:
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "-o",
            "json",
            "--dry-run",
            "record",
            "set",
            "example.com",
            "--name",
            "www",
            "--type",
            "A",
            "--content",
            "10.0.0.1",
        ],
    )
    assert r.exit_code == 0, r.stdout
    parsed = json.loads(r.stdout)
    assert parsed["dry_run"] is True
    assert parsed["request"]["method"] == "PATCH"
    assert parsed["request"]["body"][0]["changetype"] == "update"


@respx.mock
def test_record_set_require_absent_uses_changetype_add(
    cli: CliRunner,
    isolated_config: Path,
) -> None:
    """`--require-absent` maps to the strict `changetype=add` API semantics."""
    route = respx.patch(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "-o",
            "json",
            "record",
            "set",
            "example.com",
            "--name",
            "www.example.com.",
            "--type",
            "A",
            "--content",
            "10.0.0.1",
            "--require-absent",
        ],
    )
    assert r.exit_code == 0, r.stdout
    sent = json.loads(route.calls.last.request.content)
    assert sent[0]["changetype"] == "add"


@respx.mock
def test_record_set_require_exists_uses_changetype_update(
    cli: CliRunner,
    isolated_config: Path,
) -> None:
    """`--require-exists` maps to the strict `changetype=update` API semantics."""
    route = respx.patch(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "-o",
            "json",
            "record",
            "set",
            "example.com",
            "--name",
            "www.example.com.",
            "--type",
            "A",
            "--content",
            "10.0.0.9",
            "--require-exists",
        ],
    )
    assert r.exit_code == 0, r.stdout
    sent = json.loads(route.calls.last.request.content)
    assert sent[0]["changetype"] == "update"


def test_record_set_conflicting_require_flags_exits_7(
    cli: CliRunner,
    isolated_config: Path,
) -> None:
    """`--require-absent` and `--require-exists` cannot be combined."""
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "record",
            "set",
            "example.com",
            "--name",
            "www",
            "--type",
            "A",
            "--content",
            "10.0.0.1",
            "--require-absent",
            "--require-exists",
        ],
    )
    assert r.exit_code == 7, r.stdout


def test_record_set_ttl_below_floor_exits_7(
    cli: CliRunner,
    isolated_config: Path,
) -> None:
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "record",
            "set",
            "example.com",
            "--name",
            "www",
            "--type",
            "A",
            "--ttl",
            "30",
            "--content",
            "10.0.0.1",
        ],
    )
    assert r.exit_code == 7, r.stdout


def test_record_set_bad_ipv4_exits_7(
    cli: CliRunner,
    isolated_config: Path,
) -> None:
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "record",
            "set",
            "example.com",
            "--name",
            "www",
            "--type",
            "A",
            "--content",
            "not-an-ip",
        ],
    )
    assert r.exit_code == 7


# -------- record append --------


def _envelope(rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "data": rows,
        "current_page": 1,
        "last_page": 1,
        "per_page": 50,
        "total": len(rows),
    }


@respx.mock
def test_record_append_merges_with_existing(
    cli: CliRunner,
    isolated_config: Path,
) -> None:
    """`append` fetches the current rrset and PATCHes the merged record list."""
    respx.get(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(
        return_value=httpx.Response(
            200,
            json=_envelope(
                [
                    {
                        "name": "example.com.",
                        "type": "TXT",
                        "ttl": 1800,
                        "records": [
                            {"content": '"v=spf1 ~all"', "disabled": False},
                        ],
                    },
                ],
            ),
        ),
    )
    patch_route = respx.patch(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "-o",
            "json",
            "record",
            "append",
            "example.com",
            "--name",
            "@",
            "--type",
            "TXT",
            "--content",
            '"google-site-verification=xyz"',
        ],
    )
    assert r.exit_code == 0, r.stdout
    sent = json.loads(patch_route.calls.last.request.content)
    assert sent[0]["changetype"] == "update"
    # Existing TTL is preserved when --ttl is omitted.
    assert sent[0]["ttl"] == 1800
    contents = [rec["content"] for rec in sent[0]["records"]]
    assert contents == ['"v=spf1 ~all"', '"google-site-verification=xyz"']


@respx.mock
def test_record_append_creates_when_missing(
    cli: CliRunner,
    isolated_config: Path,
) -> None:
    """When no rrset exists yet, `append` creates one via changetype=add."""
    respx.get(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(200, json=_envelope([])))
    patch_route = respx.patch(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "-o",
            "json",
            "record",
            "append",
            "example.com",
            "--name",
            "_acme-challenge",
            "--type",
            "TXT",
            "--content",
            '"abc123"',
        ],
    )
    assert r.exit_code == 0, r.stdout
    sent = json.loads(patch_route.calls.last.request.content)
    assert sent[0]["changetype"] == "add"
    assert sent[0]["name"] == "_acme-challenge.example.com."
    assert sent[0]["records"] == [{"content": '"abc123"', "disabled": False}]


@respx.mock
def test_record_append_dedupes_existing_content(
    cli: CliRunner,
    isolated_config: Path,
) -> None:
    """If every --content is already present, no PATCH is sent."""
    respx.get(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(
        return_value=httpx.Response(
            200,
            json=_envelope(
                [
                    {
                        "name": "www.example.com.",
                        "type": "A",
                        "ttl": 300,
                        "records": [{"content": "10.0.0.1", "disabled": False}],
                    },
                ],
            ),
        ),
    )
    patch_route = respx.patch(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "record",
            "append",
            "example.com",
            "--name",
            "www",
            "--type",
            "A",
            "--content",
            "10.0.0.1",
        ],
    )
    assert r.exit_code == 0, r.stdout
    assert not patch_route.called
    assert "No new records to append" in r.stdout


def test_record_append_requires_content(
    cli: CliRunner,
    isolated_config: Path,
) -> None:
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "record",
            "append",
            "example.com",
            "--name",
            "www",
            "--type",
            "A",
        ],
    )
    assert r.exit_code == 7, r.stdout


# -------- record delete --------


@respx.mock
def test_record_delete_y_proceeds(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.patch(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "-o",
            "json",
            "record",
            "delete",
            "example.com",
            "--name",
            "www",
            "--type",
            "A",
        ],
        input="y\n",
    )
    assert r.exit_code == 0, r.stdout
    sent = json.loads(route.calls.last.request.content)
    assert sent[0]["changetype"] == "delete"
    assert sent[0]["records"] == []


@respx.mock
def test_record_delete_declined_exits_12(
    cli: CliRunner,
    isolated_config: Path,
) -> None:
    route = respx.patch(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "record",
            "delete",
            "example.com",
            "--name",
            "www",
            "--type",
            "A",
        ],
        input="n\n",
    )
    assert r.exit_code == 12
    assert not route.called


@respx.mock
def test_record_delete_yes_skips_prompt(
    cli: CliRunner,
    isolated_config: Path,
) -> None:
    route = respx.patch(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "-y",
            "-o",
            "json",
            "record",
            "delete",
            "example.com",
            "--name",
            "www",
            "--type",
            "A",
        ],
    )
    assert r.exit_code == 0, r.stdout
    assert route.called


def test_record_delete_dry_run_skips_prompt_and_network(
    cli: CliRunner,
    isolated_config: Path,
) -> None:
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "-o",
            "json",
            "--dry-run",
            "record",
            "delete",
            "example.com",
            "--name",
            "www",
            "--type",
            "A",
        ],
    )
    assert r.exit_code == 0, r.stdout
    parsed = json.loads(r.stdout)
    assert parsed["dry_run"] is True
    assert parsed["request"]["body"][0]["changetype"] == "delete"


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
    cli: CliRunner,
    isolated_config: Path,
    tmp_path: Path,
) -> None:
    changes = tmp_path / "changes.yaml"
    _write_changes_yaml(changes)
    route = respx.patch(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "-o",
            "json",
            "record",
            "apply",
            "example.com",
            "--from-file",
            str(changes),
        ],
        input="example.com\n",
    )
    assert r.exit_code == 0, r.stdout
    sent = json.loads(route.calls.last.request.content)
    assert len(sent) == 2
    assert {c["changetype"] for c in sent} == {"add", "delete"}


@respx.mock
def test_record_apply_wrong_confirmation_exits_12(
    cli: CliRunner,
    isolated_config: Path,
    tmp_path: Path,
) -> None:
    changes = tmp_path / "changes.yaml"
    _write_changes_yaml(changes)
    route = respx.patch(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "record",
            "apply",
            "example.com",
            "--from-file",
            str(changes),
        ],
        input="not-the-zone\n",
    )
    assert r.exit_code == 12
    assert not route.called


def test_record_apply_requires_from_file(
    cli: CliRunner,
    isolated_config: Path,
) -> None:
    r = cli.invoke(
        app,
        ["--token", "tk", "record", "apply", "example.com"],
    )
    assert r.exit_code == 7


def test_record_apply_dry_run(
    cli: CliRunner,
    isolated_config: Path,
    tmp_path: Path,
) -> None:
    changes = tmp_path / "changes.yaml"
    _write_changes_yaml(changes)
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "-o",
            "json",
            "--dry-run",
            "record",
            "apply",
            "example.com",
            "--from-file",
            str(changes),
        ],
    )
    assert r.exit_code == 0, r.stdout
    parsed = json.loads(r.stdout)
    assert parsed["dry_run"] is True
    assert parsed["request"]["method"] == "PATCH"
    assert len(parsed["request"]["body"]) == 2


# -------- record import --------


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
def test_record_import_from_file(
    cli: CliRunner,
    isolated_config: Path,
    tmp_path: Path,
) -> None:
    src = tmp_path / "rep.yaml"
    _write_replacement_yaml(src)
    route = respx.put(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "-o",
            "json",
            "record",
            "import",
            "example.com",
            "--from-file",
            str(src),
        ],
        input="example.com\n",
    )
    assert r.exit_code == 0, r.stdout
    sent = json.loads(route.calls.last.request.content)
    assert "rrsets" in sent
    assert {r["type"] for r in sent["rrsets"]} == {"SOA", "A"}


@respx.mock
def test_record_import_from_zonefile(
    cli: CliRunner,
    isolated_config: Path,
    tmp_path: Path,
) -> None:
    src = tmp_path / "example.com.zone"
    _write_zone_file(src)
    route = respx.put(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "-y",
            "-o",
            "json",
            "record",
            "import",
            "example.com",
            "--zone-file",
            str(src),
        ],
    )
    assert r.exit_code == 0, r.stdout
    sent = json.loads(route.calls.last.request.content)
    assert "rrsets" in sent
    types = {r["type"] for r in sent["rrsets"]}
    assert "SOA" in types and "NS" in types and "A" in types


def test_record_import_requires_one_source(
    cli: CliRunner,
    isolated_config: Path,
) -> None:
    r = cli.invoke(
        app,
        ["--token", "tk", "record", "import", "example.com"],
    )
    assert r.exit_code == 7


def test_record_import_rejects_both_sources(
    cli: CliRunner,
    isolated_config: Path,
    tmp_path: Path,
) -> None:
    yaml_src = tmp_path / "a.yaml"
    yaml_src.write_text("[]")
    zf = tmp_path / "a.zone"
    zf.write_text(
        "$ORIGIN example.com.\n@ 3600 IN SOA ns1.example.com. admin.example.com. 1 60 60 60 60\n",
    )
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "record",
            "import",
            "example.com",
            "--from-file",
            str(yaml_src),
            "--zone-file",
            str(zf),
        ],
    )
    assert r.exit_code == 7


# -------- record clear --------


@respx.mock
def test_record_clear_typed_confirmation_proceeds(
    cli: CliRunner,
    isolated_config: Path,
) -> None:
    route = respx.delete(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(204))
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "-o",
            "json",
            "record",
            "clear",
            "example.com",
        ],
        input="example.com\n",
    )
    assert r.exit_code == 0, r.stdout
    assert route.called


@respx.mock
def test_record_clear_wrong_confirmation_exits_12(
    cli: CliRunner,
    isolated_config: Path,
) -> None:
    route = respx.delete(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(204))
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "record",
            "clear",
            "example.com",
        ],
        input="nope\n",
    )
    assert r.exit_code == 12
    assert not route.called


def test_record_clear_dry_run(cli: CliRunner, isolated_config: Path) -> None:
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "-o",
            "json",
            "--dry-run",
            "record",
            "clear",
            "example.com",
        ],
    )
    assert r.exit_code == 0, r.stdout
    parsed = json.loads(r.stdout)
    assert parsed["dry_run"] is True
    assert parsed["request"]["method"] == "DELETE"

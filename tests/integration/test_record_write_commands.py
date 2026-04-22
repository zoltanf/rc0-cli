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
            "--token",
            "tk",
            "-o",
            "json",
            "record",
            "add",
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
            "--token",
            "tk",
            "-o",
            "json",
            "--dry-run",
            "record",
            "add",
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
    assert parsed["request"]["body"][0]["changetype"] == "add"


def test_record_add_ttl_below_floor_exits_7(
    cli: CliRunner,
    isolated_config: Path,
) -> None:
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "record",
            "add",
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


def test_record_add_bad_ipv4_exits_7(
    cli: CliRunner,
    isolated_config: Path,
) -> None:
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "record",
            "add",
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


# -------- record update --------


@respx.mock
def test_record_update_live(cli: CliRunner, isolated_config: Path) -> None:
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
            "update",
            "example.com",
            "--name",
            "www.example.com.",
            "--type",
            "A",
            "--content",
            "10.0.0.9",
        ],
    )
    assert r.exit_code == 0, r.stdout
    sent = json.loads(route.calls.last.request.content)
    assert sent[0]["changetype"] == "update"
    assert sent[0]["records"] == [{"content": "10.0.0.9", "disabled": False}]


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
            "replace-all",
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
def test_record_replace_all_from_zonefile(
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
            "replace-all",
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


def test_record_replace_all_requires_one_source(
    cli: CliRunner,
    isolated_config: Path,
) -> None:
    r = cli.invoke(
        app,
        ["--token", "tk", "record", "replace-all", "example.com"],
    )
    assert r.exit_code == 7


def test_record_replace_all_rejects_both_sources(
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
            "replace-all",
            "example.com",
            "--from-file",
            str(yaml_src),
            "--zone-file",
            str(zf),
        ],
    )
    assert r.exit_code == 7

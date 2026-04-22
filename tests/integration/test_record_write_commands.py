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

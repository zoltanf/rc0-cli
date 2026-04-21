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
def test_zone_list_default_output(cli: CliRunner, isolated_config: Path) -> None:
    respx.get("https://my.rcodezero.at/api/v2/zones").mock(
        return_value=httpx.Response(
            200,
            json=[{"domain": "example.com", "type": "master", "dnssec": "yes"}],
        ),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "zone", "list"])
    assert r.exit_code == 0, r.stdout
    parsed = json.loads(r.stdout)
    assert parsed[0]["domain"] == "example.com"


@respx.mock
def test_zone_show(cli: CliRunner, isolated_config: Path) -> None:
    respx.get("https://my.rcodezero.at/api/v2/zones/example.com").mock(
        return_value=httpx.Response(
            200,
            json={"domain": "example.com", "type": "master", "dnssec": "yes"},
        ),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "zone", "show", "example.com"])
    assert r.exit_code == 0, r.stdout
    assert json.loads(r.stdout)["domain"] == "example.com"


@respx.mock
def test_zone_status(cli: CliRunner, isolated_config: Path) -> None:
    respx.get("https://my.rcodezero.at/api/v2/zones/example.com/status").mock(
        return_value=httpx.Response(200, json={"domain": "example.com", "serial": 42}),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "zone", "status", "example.com"])
    assert r.exit_code == 0, r.stdout
    assert json.loads(r.stdout)["serial"] == 42


@respx.mock
def test_zone_list_all_auto_pages(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.get("https://my.rcodezero.at/api/v2/zones")
    route.side_effect = [
        httpx.Response(200, json=[{"domain": f"a{i}.example."} for i in range(50)]),
        httpx.Response(200, json=[{"domain": "tail.example."}]),
    ]
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "zone", "list", "--all"])
    assert r.exit_code == 0, r.stdout
    assert len(json.loads(r.stdout)) == 51

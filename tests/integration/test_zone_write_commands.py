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
            "--token",
            "tk",
            "-o",
            "json",
            "--dry-run",
            "zone",
            "create",
            "example.com",
            "--type",
            "master",
            "--master",
            "10.0.0.1",
        ],
    )
    assert r.exit_code == 0, r.stdout
    parsed = json.loads(r.stdout)
    assert parsed["dry_run"] is True
    assert parsed["request"]["method"] == "POST"
    assert parsed["request"]["url"].endswith("/api/v2/zones")
    assert parsed["request"]["headers"]["Authorization"] == "Bearer ***REDACTED***"
    assert parsed["request"]["body"] == {
        "domain": "example.com",
        "type": "master",
        "masters": ["10.0.0.1"],
    }
    assert "create" in parsed["summary"].lower()


@respx.mock
def test_zone_update_live(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.put("https://my.rcodezero.at/api/v2/zones/example.com").mock(
        return_value=httpx.Response(200, json={"status": "ok"}),
    )
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "-o",
            "json",
            "zone",
            "update",
            "example.com",
            "--master",
            "10.0.0.1",
            "--master",
            "10.0.0.2",
        ],
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
    cli: CliRunner,
    isolated_config: Path,
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
    cli: CliRunner,
    isolated_config: Path,
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
        ["--token", "tk", "-o", "json", "zone", "xfr-in", "set", "example.com", "--tsigkey", "k"],
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
    cli: CliRunner,
    isolated_config: Path,
) -> None:
    # The API accepts an empty secondaries array (it means "clear them") — make
    # sure our default serialises as []; not null.
    route = respx.post("https://my.rcodezero.at/api/v2/zones/example.com/outbound").mock(
        return_value=httpx.Response(200, json={"secondaries": [], "tsigkey": "k"}),
    )
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json", "zone", "xfr-out", "set", "example.com", "--tsigkey", "k"],
    )
    assert r.exit_code == 0, r.stdout
    assert route.called
    assert route.calls.last.request.read() == b'{"secondaries":[],"tsigkey":"k"}'


@respx.mock
def test_zone_xfr_out_show(cli: CliRunner, isolated_config: Path) -> None:
    respx.get("https://my.rcodezero.at/api/v2/zones/example.com/outbound").mock(
        return_value=httpx.Response(
            200,
            json={"secondaries": ["10.0.0.1"], "tsigkey": "k"},
        ),
    )
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json", "zone", "xfr-out", "show", "example.com"],
    )
    assert r.exit_code == 0, r.stdout
    parsed = json.loads(r.stdout)
    assert parsed["tsigkey"] == "k"
    assert parsed["secondaries"] == ["10.0.0.1"]


@respx.mock
def test_zone_xfr_out_unset(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.delete("https://my.rcodezero.at/api/v2/zones/example.com/outbound").mock(
        return_value=httpx.Response(204),
    )
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json", "zone", "xfr-out", "unset", "example.com"],
    )
    assert r.exit_code == 0, r.stdout
    assert route.called

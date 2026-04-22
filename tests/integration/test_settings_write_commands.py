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
        [
            "--token",
            "tk",
            "-o",
            "json",
            "settings",
            "secondaries",
            "set",
            "--ip",
            "10.0.0.1",
            "--ip",
            "10.0.0.2",
        ],
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
        [
            "--token",
            "tk",
            "-o",
            "json",
            "--dry-run",
            "settings",
            "secondaries",
            "set",
            "--ip",
            "10.0.0.1",
        ],
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
        ["--token", "tk", "-o", "json", "settings", "tsig-in", "set", "k1"],
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
        ["--token", "tk", "-o", "json", "settings", "tsig-out", "set", "k1"],
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

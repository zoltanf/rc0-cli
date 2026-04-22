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
        [
            "--token",
            "tk",
            "-o",
            "json",
            "tsig",
            "add",
            "k1",
            "--algorithm",
            "hmac-sha256",
            "--secret",
            "abc",
        ],
    )
    assert r.exit_code == 0, r.stdout
    assert route.called
    assert route.calls.last.request.read() == (
        b'{"name":"k1","algorithm":"hmac-sha256","secret":"abc"}'
    )


def test_tsig_add_rejects_bad_algorithm(cli: CliRunner, isolated_config: Path) -> None:
    r = cli.invoke(
        app,
        ["--token", "tk", "tsig", "add", "k1", "--algorithm", "hmac-sha-BROKEN", "--secret", "abc"],
    )
    assert r.exit_code == 2, r.stdout  # Typer usage error


def test_tsig_add_dry_run(cli: CliRunner, isolated_config: Path) -> None:
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "-o",
            "json",
            "--dry-run",
            "tsig",
            "add",
            "k1",
            "--algorithm",
            "hmac-sha256",
            "--secret",
            "abc",
        ],
    )
    assert r.exit_code == 0, r.stdout
    parsed = json.loads(r.stdout)
    assert parsed["dry_run"] is True
    assert parsed["request"]["body"] == {
        "name": "k1",
        "algorithm": "hmac-sha256",
        "secret": "abc",
    }


@respx.mock
def test_tsig_update_live(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.put("https://my.rcodezero.at/api/v2/tsig/k1").mock(
        return_value=httpx.Response(200, json={"status": "ok"}),
    )
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "-o",
            "json",
            "tsig",
            "update",
            "k1",
            "--algorithm",
            "hmac-sha512",
            "--secret",
            "xyz",
        ],
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


def test_tsig_delete_dry_run_skips_prompt_and_network(
    cli: CliRunner, isolated_config: Path,
) -> None:
    # No respx route registered; if the command reached the network, respx
    # would 500. --dry-run must skip both the confirmation prompt and the HTTP
    # call entirely.
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json", "--dry-run", "tsig", "delete", "k1"],
    )
    assert r.exit_code == 0, r.stdout
    parsed = json.loads(r.stdout)
    assert parsed["dry_run"] is True
    assert parsed["request"]["method"] == "DELETE"
    assert parsed["request"]["url"].endswith("/api/v2/tsig/k1")
    assert parsed["side_effects"] == ["deletes_tsig_key"]

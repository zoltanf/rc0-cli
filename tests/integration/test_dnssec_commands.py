"""Integration tests for `rc0 dnssec` commands."""

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


_OK = {"status": "ok"}
_ZONE = "example.com"
_BASE = "https://my.rcodezero.at/api/v2/zones"
_TEST_URL = "https://my-test.rcodezero.at"


def _invoke(cli: CliRunner, *args: str, input: str | None = None) -> object:
    return cli.invoke(app, ["--token", "tk", "-o", "json", *args], input=input)


# ====================================================================== sign


def test_sign_dry_run(cli: CliRunner, isolated_config: Path) -> None:
    r = _invoke(cli, "--dry-run", "dnssec", "sign", _ZONE)
    assert r.exit_code == 0, r.output
    parsed = json.loads(r.output)
    assert parsed["dry_run"] is True
    assert parsed["request"]["method"] == "POST"
    assert parsed["request"]["url"].endswith(f"/api/v2/zones/{_ZONE}/sign")
    assert parsed["request"].get("body") is None


@respx.mock
def test_sign_live_no_flags(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.post(f"{_BASE}/{_ZONE}/sign").mock(
        return_value=httpx.Response(200, json=_OK),
    )
    r = _invoke(cli, "dnssec", "sign", _ZONE)
    assert r.exit_code == 0, r.output
    assert route.called
    assert json.loads(r.output) == _OK
    url = str(route.calls.last.request.url)
    assert "ignoresafetyperiod" not in url
    assert "enable_cds_cdnskey" not in url


@respx.mock
def test_sign_with_flags(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.post(f"{_BASE}/{_ZONE}/sign").mock(
        return_value=httpx.Response(200, json=_OK),
    )
    r = _invoke(
        cli,
        "dnssec",
        "sign",
        _ZONE,
        "--ignore-safety-period",
        "--enable-cds-cdnskey",
    )
    assert r.exit_code == 0, r.output
    url = str(route.calls.last.request.url)
    assert "ignoresafetyperiod=1" in url
    assert "enable_cds_cdnskey=1" in url


# ===================================================================== unsign


def test_unsign_no_force_exits_7(cli: CliRunner, isolated_config: Path) -> None:
    r = _invoke(cli, "dnssec", "unsign", _ZONE)
    assert r.exit_code == 7


def test_unsign_force_dry_run(cli: CliRunner, isolated_config: Path) -> None:
    r = _invoke(cli, "--dry-run", "dnssec", "unsign", _ZONE, "--force")
    assert r.exit_code == 0, r.output
    parsed = json.loads(r.output)
    assert parsed["dry_run"] is True
    assert parsed["request"]["url"].endswith(f"/api/v2/zones/{_ZONE}/unsign")


@respx.mock
def test_unsign_force_yes(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.post(f"{_BASE}/{_ZONE}/unsign").mock(
        return_value=httpx.Response(200, json=_OK),
    )
    r = _invoke(cli, "-y", "dnssec", "unsign", _ZONE, "--force")
    assert r.exit_code == 0, r.output
    assert route.called


@respx.mock
def test_unsign_force_confirmed(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.post(f"{_BASE}/{_ZONE}/unsign").mock(
        return_value=httpx.Response(200, json=_OK),
    )
    r = _invoke(cli, "dnssec", "unsign", _ZONE, "--force", input="y\n")
    assert r.exit_code == 0, r.output
    assert route.called


def test_unsign_force_declined(cli: CliRunner, isolated_config: Path) -> None:
    r = _invoke(cli, "dnssec", "unsign", _ZONE, "--force", input="n\n")
    assert r.exit_code == 12


# ================================================================= keyrollover


@respx.mock
def test_keyrollover_confirmed(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.post(f"{_BASE}/{_ZONE}/keyrollover").mock(
        return_value=httpx.Response(200, json=_OK),
    )
    r = _invoke(cli, "dnssec", "keyrollover", _ZONE, input="y\n")
    assert r.exit_code == 0, r.output
    assert route.called


def test_keyrollover_declined(cli: CliRunner, isolated_config: Path) -> None:
    r = _invoke(cli, "dnssec", "keyrollover", _ZONE, input="n\n")
    assert r.exit_code == 12


@respx.mock
def test_keyrollover_yes_flag(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.post(f"{_BASE}/{_ZONE}/keyrollover").mock(
        return_value=httpx.Response(200, json=_OK),
    )
    r = _invoke(cli, "-y", "dnssec", "keyrollover", _ZONE)
    assert r.exit_code == 0, r.output
    assert route.called


def test_keyrollover_dry_run(cli: CliRunner, isolated_config: Path) -> None:
    r = _invoke(cli, "--dry-run", "dnssec", "keyrollover", _ZONE)
    assert r.exit_code == 0, r.output
    parsed = json.loads(r.output)
    assert parsed["request"]["url"].endswith(f"/api/v2/zones/{_ZONE}/keyrollover")


# ====================================================================== ack-ds


@respx.mock
def test_ack_ds(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.post(f"{_BASE}/{_ZONE}/dsupdate").mock(
        return_value=httpx.Response(200, json=_OK),
    )
    r = _invoke(cli, "dnssec", "ack-ds", _ZONE)
    assert r.exit_code == 0, r.output
    assert route.called
    assert json.loads(r.output) == _OK


def test_ack_ds_dry_run(cli: CliRunner, isolated_config: Path) -> None:
    r = _invoke(cli, "--dry-run", "dnssec", "ack-ds", _ZONE)
    assert r.exit_code == 0, r.output
    parsed = json.loads(r.output)
    assert parsed["request"]["url"].endswith(f"/api/v2/zones/{_ZONE}/dsupdate")


# ===================================================================== simulate


def test_simulate_blocked_on_prod(cli: CliRunner, isolated_config: Path) -> None:
    r = _invoke(cli, "dnssec", "simulate", "dsseen", _ZONE)
    assert r.exit_code == 1
    assert "test environments" in r.output


def test_simulate_dry_run_still_blocked_on_prod(cli: CliRunner, isolated_config: Path) -> None:
    r = _invoke(cli, "--dry-run", "dnssec", "simulate", "dsseen", _ZONE)
    assert r.exit_code == 1
    assert "test environments" in r.output


@respx.mock
def test_simulate_dsseen_test_env(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.post(
        f"{_TEST_URL}/api/v2/zones/{_ZONE}/simulate/dsseen",
    ).mock(return_value=httpx.Response(200, json=_OK))
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "-o",
            "json",
            "--api-url",
            _TEST_URL,
            "dnssec",
            "simulate",
            "dsseen",
            _ZONE,
        ],
    )
    assert r.exit_code == 0, r.output
    assert route.called


@respx.mock
def test_simulate_dsremoved_test_env(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.post(
        f"{_TEST_URL}/api/v2/zones/{_ZONE}/simulate/dsremoved",
    ).mock(return_value=httpx.Response(200, json=_OK))
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "-o",
            "json",
            "--api-url",
            _TEST_URL,
            "dnssec",
            "simulate",
            "dsremoved",
            _ZONE,
        ],
    )
    assert r.exit_code == 0, r.output
    assert route.called

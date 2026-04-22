"""Integration tests for `rc0 acme` commands."""

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
_BASE_V1 = "https://my.rcodezero.at/api/v1/acme"

_CHALLENGE_PAGE = {
    "current_page": 1,
    "data": [
        {
            "name": f"_acme-challenge.{_ZONE}.",
            "type": "TXT",
            "ttl": 60,
            "records": [{"content": "mytoken", "disabled": False}],
        }
    ],
    "from": 1,
    "last_page": 1,
    "next_page_url": "null",
    "path": f"https://my.rcodezero.at/api/v1/acme/zones/{_ZONE}/rrsets",
    "per_page": 100,
    "prev_page_url": "null",
    "to": 1,
    "total": 1,
}


def _invoke(cli: CliRunner, *args: str, input: str | None = None) -> object:
    return cli.invoke(app, ["--token", "tk", "-o", "json", *args], input=input)


# ================================================================ zone-exists


@respx.mock
def test_zone_exists_found(cli: CliRunner, isolated_config: Path) -> None:
    respx.get(f"{_BASE_V1}/{_ZONE}").mock(return_value=httpx.Response(200, json=["found"]))
    r = _invoke(cli, "acme", "zone-exists", _ZONE)
    assert r.exit_code == 0, r.output
    assert json.loads(r.output) == ["found"]


@respx.mock
def test_zone_exists_not_found(cli: CliRunner, isolated_config: Path) -> None:
    respx.get(f"{_BASE_V1}/{_ZONE}").mock(
        return_value=httpx.Response(404, json={"message": "not found"})
    )
    r = _invoke(cli, "acme", "zone-exists", _ZONE)
    assert r.exit_code == 6


# ============================================================= list-challenges


@respx.mock
def test_list_challenges(cli: CliRunner, isolated_config: Path) -> None:
    respx.get(f"{_BASE_V1}/zones/{_ZONE}/rrsets").mock(
        return_value=httpx.Response(200, json=_CHALLENGE_PAGE)
    )
    r = _invoke(cli, "acme", "list-challenges", _ZONE)
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    assert isinstance(data, list)
    assert data[0]["type"] == "TXT"


# ============================================================== add-challenge


def test_add_challenge_dry_run(cli: CliRunner, isolated_config: Path) -> None:
    r = _invoke(cli, "--dry-run", "acme", "add-challenge", _ZONE, "--value", "mytoken")
    assert r.exit_code == 0, r.output
    parsed = json.loads(r.output)
    assert parsed["dry_run"] is True
    req = parsed["request"]
    assert req["method"] == "PATCH"
    assert req["url"].endswith(f"/api/v1/acme/zones/{_ZONE}/rrsets")
    body = req["body"]
    assert body[0]["changetype"] == "add"
    assert body[0]["records"][0]["content"] == "mytoken"
    assert body[0]["name"] == f"_acme-challenge.{_ZONE}."


def test_add_challenge_dry_run_custom_ttl(cli: CliRunner, isolated_config: Path) -> None:
    r = _invoke(cli, "--dry-run", "acme", "add-challenge", _ZONE, "--value", "tok", "--ttl", "300")
    assert r.exit_code == 0, r.output
    body = json.loads(r.output)["request"]["body"]
    assert body[0]["ttl"] == 300


@respx.mock
def test_add_challenge_live(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.patch(f"{_BASE_V1}/zones/{_ZONE}/rrsets").mock(
        return_value=httpx.Response(200, json=_OK)
    )
    r = _invoke(cli, "acme", "add-challenge", _ZONE, "--value", "mytoken")
    assert r.exit_code == 0, r.output
    assert route.called
    assert json.loads(r.output) == _OK
    sent_body = json.loads(route.calls.last.request.content)
    assert sent_body[0]["changetype"] == "add"


# =========================================================== remove-challenge


def test_remove_challenge_dry_run(cli: CliRunner, isolated_config: Path) -> None:
    r = _invoke(cli, "--dry-run", "acme", "remove-challenge", _ZONE)
    assert r.exit_code == 0, r.output
    parsed = json.loads(r.output)
    assert parsed["dry_run"] is True
    req = parsed["request"]
    assert req["method"] == "PATCH"
    body = req["body"]
    assert body[0]["changetype"] == "delete"
    assert body[0]["name"] == f"_acme-challenge.{_ZONE}."


@respx.mock
def test_remove_challenge_confirmed(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.patch(f"{_BASE_V1}/zones/{_ZONE}/rrsets").mock(
        return_value=httpx.Response(200, json=_OK)
    )
    r = _invoke(cli, "acme", "remove-challenge", _ZONE, input="y\n")
    assert r.exit_code == 0, r.output
    assert route.called


def test_remove_challenge_declined(cli: CliRunner, isolated_config: Path) -> None:
    r = _invoke(cli, "acme", "remove-challenge", _ZONE, input="n\n")
    assert r.exit_code == 12


@respx.mock
def test_remove_challenge_yes_flag(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.patch(f"{_BASE_V1}/zones/{_ZONE}/rrsets").mock(
        return_value=httpx.Response(200, json=_OK)
    )
    r = _invoke(cli, "-y", "acme", "remove-challenge", _ZONE)
    assert r.exit_code == 0, r.output
    assert route.called


# ================================================================= 403 hint


@respx.mock
def test_acme_403_exits_5(cli: CliRunner, isolated_config: Path) -> None:
    respx.patch(f"{_BASE_V1}/zones/{_ZONE}/rrsets").mock(
        return_value=httpx.Response(403, json={"message": "Forbidden"})
    )
    r = _invoke(cli, "acme", "add-challenge", _ZONE, "--value", "tok")
    assert r.exit_code == 5

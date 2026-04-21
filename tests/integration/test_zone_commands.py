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


def _envelope(
    rows: list[dict[str, object]],
    *,
    current_page: int,
    last_page: int,
) -> dict[str, object]:
    return {
        "data": rows,
        "current_page": current_page,
        "last_page": last_page,
        "per_page": 50,
        "total": len(rows) if current_page == last_page else last_page * 50,
        "from": (current_page - 1) * 50 + 1,
        "to": (current_page - 1) * 50 + len(rows),
    }


@pytest.fixture
def cli() -> CliRunner:
    return CliRunner()


@respx.mock
def test_zone_list_default_output(cli: CliRunner, isolated_config: Path) -> None:
    respx.get("https://my.rcodezero.at/api/v2/zones").mock(
        return_value=httpx.Response(
            200,
            json=_envelope(
                [{"id": 1, "domain": "example.com", "type": "MASTER", "dnssec": "yes"}],
                current_page=1,
                last_page=1,
            ),
        ),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "zone", "list"])
    assert r.exit_code == 0, r.stdout
    parsed = json.loads(r.stdout)
    assert parsed[0]["domain"] == "example.com"
    assert parsed[0]["type"] == "MASTER"


@respx.mock
def test_zone_show(cli: CliRunner, isolated_config: Path) -> None:
    respx.get("https://my.rcodezero.at/api/v2/zones/example.com").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 1,
                "domain": "example.com",
                "type": "MASTER",
                "dnssec": "yes",
                "serial": 2026042100,
            },
        ),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "zone", "show", "example.com"])
    assert r.exit_code == 0, r.stdout
    body = json.loads(r.stdout)
    assert body["domain"] == "example.com"
    assert body["serial"] == 2026042100


@respx.mock
def test_zone_status(cli: CliRunner, isolated_config: Path) -> None:
    respx.get("https://my.rcodezero.at/api/v2/zones/example.com/status").mock(
        return_value=httpx.Response(200, json={"zone_disabled": False}),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "zone", "status", "example.com"])
    assert r.exit_code == 0, r.stdout
    assert json.loads(r.stdout)["zone_disabled"] is False


@respx.mock
def test_zone_list_all_auto_pages(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.get("https://my.rcodezero.at/api/v2/zones")
    route.side_effect = [
        httpx.Response(
            200,
            json=_envelope(
                [{"id": i, "domain": f"a{i}.example.", "type": "MASTER"} for i in range(50)],
                current_page=1,
                last_page=2,
            ),
        ),
        httpx.Response(
            200,
            json=_envelope(
                [{"id": 99, "domain": "tail.example.", "type": "MASTER"}],
                current_page=2,
                last_page=2,
            ),
        ),
    ]
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "zone", "list", "--all"])
    assert r.exit_code == 0, r.stdout
    assert len(json.loads(r.stdout)) == 51


def test_zone_list_rejects_page_with_all(cli: CliRunner, isolated_config: Path) -> None:
    r = cli.invoke(app, ["--token", "tk", "zone", "list", "--all", "--page", "2"])
    # Exit code 7 is ValidationError (mission plan §11) — proves the right
    # exception fired. We don't assert on the rendered message because Click's
    # Rich-bordered error panel word-wraps based on terminal width and splits
    # the substring differently on CI vs. local runs.
    assert r.exit_code == 7, r.stdout


def test_zone_list_rejects_zero_page_size(cli: CliRunner, isolated_config: Path) -> None:
    r = cli.invoke(app, ["--token", "tk", "zone", "list", "--page-size", "0"])
    # Typer/Click usage error for out-of-range value.
    assert r.exit_code == 2, r.stdout

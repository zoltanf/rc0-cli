"""Report CLI integration tests."""

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
    current_page: int = 1,
    last_page: int = 1,
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
def test_problematic_zones_default(cli: CliRunner, isolated_config: Path) -> None:
    respx.get("https://my.rcodezero.at/api/v2/reports/problematiczones").mock(
        return_value=httpx.Response(200, json=_envelope([{"domain": "bad.example."}])),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "report", "problematic-zones"])
    assert r.exit_code == 0, r.stdout
    assert json.loads(r.stdout)[0]["domain"] == "bad.example."


@respx.mock
def test_problematic_zones_all_auto_pages(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.get("https://my.rcodezero.at/api/v2/reports/problematiczones")
    route.side_effect = [
        httpx.Response(
            200,
            json=_envelope([{"domain": "a.example."}], current_page=1, last_page=2),
        ),
        httpx.Response(
            200,
            json=_envelope([{"domain": "b.example."}], current_page=2, last_page=2),
        ),
    ]
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json", "report", "problematic-zones", "--all"],
    )
    assert r.exit_code == 0, r.stdout
    assert [row["domain"] for row in json.loads(r.stdout)] == ["a.example.", "b.example."]


@respx.mock
def test_nxdomains_passes_day_param(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.get(
        "https://my.rcodezero.at/api/v2/reports/nxdomains",
        params={"day": "today"},
    ).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "date": "2026-04-21",
                    "domain": "d.example.",
                    "qname": "x.d.example.",
                    "qtype": "A",
                    "querycount": 5,
                },
            ],
        ),
    )
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json", "report", "nxdomains", "--day", "today"],
    )
    assert r.exit_code == 0, r.stdout
    assert route.called
    assert json.loads(r.stdout)[0]["querycount"] == 5


@respx.mock
def test_accounting_passes_month_param(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.get(
        "https://my.rcodezero.at/api/v2/reports/accounting",
        params={"month": "2026-04"},
    ).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "account": "acct",
                    "date": "2026-04-01",
                    "domain_count": 5,
                    "domain_count_dnssec": 1,
                    "query_count": 100,
                    "records_count": 50,
                },
            ],
        ),
    )
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json", "report", "accounting", "--month", "2026-04"],
    )
    assert r.exit_code == 0, r.stdout
    assert route.called
    assert json.loads(r.stdout)[0]["account"] == "acct"


@respx.mock
def test_queryrates_passes_month_and_include_nx(
    cli: CliRunner,
    isolated_config: Path,
) -> None:
    route = respx.get(
        "https://my.rcodezero.at/api/v2/reports/queryrates",
        params={"month": "2026-04", "include_nx": "1"},
    ).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "date": "2026-04-01",
                    "domain": "x.example.",
                    "querycount": 10,
                    "nx_querycount": 1,
                },
            ],
        ),
    )
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "-o",
            "json",
            "report",
            "queryrates",
            "--month",
            "2026-04",
            "--include-nx",
        ],
    )
    assert r.exit_code == 0, r.stdout
    assert route.called
    assert json.loads(r.stdout)[0]["nx_querycount"] == 1


@respx.mock
def test_domainlist(cli: CliRunner, isolated_config: Path) -> None:
    respx.get("https://my.rcodezero.at/api/v2/reports/domainlist").mock(
        return_value=httpx.Response(
            200,
            json=[{"domain": "example.com.", "serial": 2026042100}],
        ),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "report", "domainlist"])
    assert r.exit_code == 0, r.stdout
    assert json.loads(r.stdout)[0]["serial"] == 2026042100

"""Sites CLI integration tests."""

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


_SITES = {
    "sites": [
        {
            "name": "ams",
            "city": "Amsterdam",
            "countrycode": "NL",
            "country": "Netherlands",
            "continentcode": "EU",
            "continent": "Europe",
            "latitude": 52.3731,
            "longitude": 4.8924,
            "status": "active",
            "clouds": ["cloud1", "cloud2"],
        },
        {
            "name": "vie",
            "city": "Vienna",
            "countrycode": "AT",
            "country": "Austria",
            "continentcode": "EU",
            "continent": "Europe",
            "latitude": 48.2082,
            "longitude": 16.3738,
            "status": "active",
            "clouds": ["cloud1"],
        },
    ],
}


@pytest.fixture
def cli() -> CliRunner:
    return CliRunner()


@respx.mock
def test_sites_list_json(cli: CliRunner, isolated_config: Path) -> None:
    respx.get("https://my.rcodezero.at/api/v2/sites").mock(
        return_value=httpx.Response(200, json=_SITES),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "sites", "list"])
    assert r.exit_code == 0, r.stdout
    rows = json.loads(r.stdout)
    assert [row["name"] for row in rows] == ["ams", "vie"]
    assert rows[0]["clouds"] == ["cloud1", "cloud2"]


@respx.mock
def test_sites_list_csv_columns(cli: CliRunner, isolated_config: Path) -> None:
    """CSV output must emit the declared column order with a header row."""
    respx.get("https://my.rcodezero.at/api/v2/sites").mock(
        return_value=httpx.Response(200, json=_SITES),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "csv", "sites", "list"])
    assert r.exit_code == 0, r.stdout
    header = r.stdout.splitlines()[0]
    assert header.startswith("name,city,countrycode,continent,latitude,longitude,status,clouds")
    assert "ams" in r.stdout and "vie" in r.stdout


@respx.mock
def test_sites_list_empty_body_returns_empty_list(cli: CliRunner, isolated_config: Path) -> None:
    """Empty API body must not crash — returns [] gracefully."""
    respx.get("https://my.rcodezero.at/api/v2/sites").mock(
        return_value=httpx.Response(200, content=b""),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "sites", "list"])
    assert r.exit_code == 0, r.stdout
    assert json.loads(r.stdout) == []

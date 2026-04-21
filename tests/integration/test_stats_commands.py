"""Stats CLI integration tests."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

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


@pytest.mark.parametrize(
    ("cli_path", "api_path", "body"),
    [
        (
            ["stats", "queries"],
            "/api/v2/stats/querycounts",
            [{"date": "2026-04-21", "count": 100, "nxcount": 3}],
        ),
        (
            ["stats", "topzones"],
            "/api/v2/stats/topzones",
            [{"domain": "example.com", "count": 9}],
        ),
        (
            ["stats", "countries"],
            "/api/v2/stats/countries",
            [
                {
                    "cc": "AT",
                    "country": "Austria",
                    "qc": 7,
                    "region": "Europe",
                    "subregion": "Western",
                },
            ],
        ),
        (
            ["stats", "zone", "queries", "example.com"],
            "/api/v2/zones/example.com/stats/queries",
            [{"date": "2026-04-21", "qcount": 42, "nxcount": 1}],
        ),
    ],
)
@respx.mock
def test_stats_non_deprecated(
    cli: CliRunner,
    isolated_config: Path,
    cli_path: list[str],
    api_path: str,
    body: list[dict[str, Any]],
) -> None:
    respx.get(f"https://my.rcodezero.at{api_path}").mock(
        return_value=httpx.Response(200, json=body),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", *cli_path])
    assert r.exit_code == 0, r.stdout
    assert json.loads(r.stdout) == body


@respx.mock
def test_stats_topmagnitude_emits_deprecation_warning(
    cli: CliRunner,
    isolated_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RC0_SUPPRESS_DEPRECATED", raising=False)
    respx.get("https://my.rcodezero.at/api/v2/stats/topmagnitude").mock(
        return_value=httpx.Response(200, json=[]),
    )
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json", "stats", "topmagnitude"],
    )
    assert r.exit_code == 0, r.stdout
    assert "[DEPRECATED]" in (r.stderr or "")


@respx.mock
def test_stats_zone_magnitude_emits_deprecation_warning(
    cli: CliRunner,
    isolated_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RC0_SUPPRESS_DEPRECATED", raising=False)
    respx.get("https://my.rcodezero.at/api/v2/zones/example.com/stats/magnitude").mock(
        return_value=httpx.Response(200, json=[]),
    )
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json", "stats", "zone", "magnitude", "example.com"],
    )
    assert r.exit_code == 0, r.stdout
    assert "[DEPRECATED]" in (r.stderr or "")

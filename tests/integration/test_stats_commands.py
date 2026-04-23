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
def test_stats_queries_sends_days_param(cli: CliRunner, isolated_config: Path) -> None:
    """``--days N`` must be forwarded to /stats/querycounts as a query parameter."""
    route = respx.get("https://my.rcodezero.at/api/v2/stats/querycounts").mock(
        return_value=httpx.Response(200, json=[]),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "stats", "queries", "--days", "7"])
    assert r.exit_code == 0, r.stdout
    assert route.called
    assert dict(route.calls[0].request.url.params)["days"] == "7"


@respx.mock
def test_stats_topzones_sends_days_param(cli: CliRunner, isolated_config: Path) -> None:
    """``--days N`` must be forwarded to /stats/topzones as a query parameter."""
    route = respx.get("https://my.rcodezero.at/api/v2/stats/topzones").mock(
        return_value=httpx.Response(200, json=[]),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "stats", "topzones", "--days", "14"])
    assert r.exit_code == 0, r.stdout
    assert route.called
    assert dict(route.calls[0].request.url.params)["days"] == "14"


@respx.mock
def test_stats_queries_omits_days_when_not_provided(
    cli: CliRunner,
    isolated_config: Path,
) -> None:
    """Without ``--days`` the request must not send a ``days`` param (API default)."""
    route = respx.get("https://my.rcodezero.at/api/v2/stats/querycounts").mock(
        return_value=httpx.Response(200, json=[]),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "stats", "queries"])
    assert r.exit_code == 0, r.stdout
    assert "days" not in dict(route.calls[0].request.url.params)


def test_stats_queries_rejects_days_out_of_range(cli: CliRunner, isolated_config: Path) -> None:
    """``--days`` must be clamped to [1, 180] by Typer validation."""
    r = cli.invoke(app, ["--token", "tk", "stats", "queries", "--days", "200"])
    assert r.exit_code == 2


@respx.mock
def test_stats_zone_queries_slices_days_client_side(
    cli: CliRunner,
    isolated_config: Path,
) -> None:
    """The zone-queries endpoint has no ``days`` param; ``--days`` must slice client-side."""
    full_history = [
        {"date": f"2026-04-{d:02d}", "qcount": d * 10, "nxcount": d} for d in range(1, 21)
    ]
    route = respx.get("https://my.rcodezero.at/api/v2/zones/example.com/stats/queries").mock(
        return_value=httpx.Response(200, json=full_history),
    )
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json", "stats", "zone", "queries", "example.com", "--days", "5"],
    )
    assert r.exit_code == 0, r.stdout
    assert "days" not in dict(route.calls[0].request.url.params)
    rows = json.loads(r.stdout)
    assert len(rows) == 5
    assert [row["date"] for row in rows] == [
        "2026-04-16",
        "2026-04-17",
        "2026-04-18",
        "2026-04-19",
        "2026-04-20",
    ]


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

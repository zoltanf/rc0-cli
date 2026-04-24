"""Record CLI integration tests."""

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


def _envelope(rows, *, current_page=1, last_page=1):
    return {
        "data": rows,
        "current_page": current_page,
        "last_page": last_page,
        "per_page": 50,
        "total": len(rows),
    }


@pytest.fixture
def cli() -> CliRunner:
    return CliRunner()


@respx.mock
def test_record_list_default_fetches_all_pages(cli: CliRunner, isolated_config: Path) -> None:
    """Regression: default behaviour must not silently truncate on multi-page data."""
    route = respx.get("https://my.rcodezero.at/api/v2/zones/example.com/rrsets")
    route.side_effect = [
        httpx.Response(
            200,
            json=_envelope(
                [
                    {
                        "name": f"r{i}.example.com.",
                        "type": "A",
                        "ttl": 300,
                        "records": [{"content": "10.0.0.1", "disabled": False}],
                    }
                    for i in range(50)
                ],
                current_page=1,
                last_page=2,
            ),
        ),
        httpx.Response(
            200,
            json=_envelope(
                [
                    {
                        "name": "tail.example.com.",
                        "type": "A",
                        "ttl": 300,
                        "records": [{"content": "10.0.0.2", "disabled": False}],
                    },
                ],
                current_page=2,
                last_page=2,
            ),
        ),
    ]
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "record", "list", "example.com"])
    assert r.exit_code == 0, r.stdout
    rows = json.loads(r.stdout)
    assert len(rows) == 51
    assert route.call_count == 2
    assert (r.stderr or "") == ""


@respx.mock
def test_record_list_page_warns_on_truncation(cli: CliRunner, isolated_config: Path) -> None:
    """Explicit --page leaves rows on the table → stderr warning must fire."""
    respx.get("https://my.rcodezero.at/api/v2/zones/example.com/rrsets").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "name": f"r{i}.example.com.",
                        "type": "A",
                        "ttl": 300,
                        "records": [{"content": "10.0.0.1", "disabled": False}],
                    }
                    for i in range(50)
                ],
                "current_page": 1,
                "last_page": 5,
                "per_page": 50,
                "total": 237,
            },
        ),
    )
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json", "record", "list", "example.com", "--page", "1"],
    )
    assert r.exit_code == 0, r.stdout
    assert len(json.loads(r.stdout)) == 50
    stderr = r.stderr or ""
    assert "showing page 1 of 5" in stderr
    assert "50 of 237 rows" in stderr
    assert "Omit --page" in stderr


@respx.mock
def test_record_list_quiet_suppresses_warning(cli: CliRunner, isolated_config: Path) -> None:
    """-q must silence the --page truncation warning."""
    respx.get("https://my.rcodezero.at/api/v2/zones/example.com/rrsets").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "name": f"r{i}.example.com.",
                        "type": "A",
                        "ttl": 300,
                        "records": [{"content": "10.0.0.1", "disabled": False}],
                    }
                    for i in range(50)
                ],
                "current_page": 1,
                "last_page": 5,
                "per_page": 50,
                "total": 237,
            },
        ),
    )
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "-q",
            "-o",
            "json",
            "record",
            "list",
            "example.com",
            "--page",
            "1",
        ],
    )
    assert r.exit_code == 0, r.stdout
    assert (r.stderr or "") == ""


@respx.mock
def test_record_list(cli: CliRunner, isolated_config: Path) -> None:
    respx.get("https://my.rcodezero.at/api/v2/zones/example.com/rrsets").mock(
        return_value=httpx.Response(
            200,
            json=_envelope(
                [
                    {
                        "name": "www.example.com.",
                        "type": "A",
                        "ttl": 300,
                        "records": [{"content": "10.0.0.1", "disabled": False}],
                    }
                ]
            ),
        ),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "record", "list", "example.com"])
    assert r.exit_code == 0, r.stdout
    rows = json.loads(r.stdout)
    assert rows[0]["type"] == "A"
    assert rows[0]["records"][0]["content"] == "10.0.0.1"


@respx.mock
def test_record_list_with_filters(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.get(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
        params={"names": "www.example.com.", "types": "A", "page": 1, "page_size": 50},
    ).mock(return_value=httpx.Response(200, json=_envelope([])))
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "-o",
            "json",
            "record",
            "list",
            "example.com",
            "--name",
            "www.example.com.",
            "--type",
            "A",
        ],
    )
    assert r.exit_code == 0, r.stdout
    assert route.called


@respx.mock
def test_record_export_bind(cli: CliRunner, isolated_config: Path) -> None:
    respx.get("https://my.rcodezero.at/api/v2/zones/example.com/rrsets").mock(
        return_value=httpx.Response(
            200,
            json=_envelope(
                [
                    {
                        "name": "example.com.",
                        "type": "SOA",
                        "ttl": 3600,
                        "records": [
                            {
                                "content": (
                                    "ns1.example.com. admin.example.com. 1 7200 3600 1209600 3600"
                                ),
                                "disabled": False,
                            }
                        ],
                    },
                    {
                        "name": "www.example.com.",
                        "type": "A",
                        "ttl": 300,
                        "records": [{"content": "10.0.0.1", "disabled": False}],
                    },
                ]
            ),
        ),
    )
    r = cli.invoke(app, ["--token", "tk", "record", "export", "example.com"])
    assert r.exit_code == 0, r.stdout
    assert "$ORIGIN example.com." in r.stdout
    assert "10.0.0.1" in r.stdout


@respx.mock
def test_record_export_json(cli: CliRunner, isolated_config: Path) -> None:
    respx.get("https://my.rcodezero.at/api/v2/zones/example.com/rrsets").mock(
        return_value=httpx.Response(
            200,
            json=_envelope(
                [
                    {
                        "name": "www.example.com.",
                        "type": "A",
                        "ttl": 300,
                        "records": [{"content": "10.0.0.1", "disabled": False}],
                    }
                ]
            ),
        ),
    )
    r = cli.invoke(app, ["--token", "tk", "record", "export", "example.com", "-f", "json"])
    assert r.exit_code == 0, r.stdout
    parsed = json.loads(r.stdout)
    assert parsed[0]["type"] == "A"

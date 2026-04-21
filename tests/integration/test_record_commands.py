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
                                "content": "ns1.example.com. admin.example.com. 1 7200 3600 1209600 3600",
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

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
def test_record_list_apex_name_filter(cli: CliRunner, isolated_config: Path) -> None:
    """`--name @` must resolve to the zone apex FQDN before hitting the API."""
    route = respx.get(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
        params={"names": "example.com.", "types": "TXT", "page": 1, "page_size": 50},
    ).mock(
        return_value=httpx.Response(
            200,
            json=_envelope(
                [
                    {
                        "name": "example.com.",
                        "type": "TXT",
                        "ttl": 3600,
                        "records": [
                            {"content": '"v=spf1 -all"', "disabled": False},
                        ],
                    },
                ],
            ),
        ),
    )
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
            "@",
            "--type",
            "TXT",
        ],
    )
    assert r.exit_code == 0, r.stdout
    assert route.called
    rows = json.loads(r.stdout)
    assert rows[0]["name"] == "example.com."


@respx.mock
def test_record_list_short_name_qualified(cli: CliRunner, isolated_config: Path) -> None:
    """A bare label like `www` must be auto-qualified to `www.example.com.`."""
    route = respx.get(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
        params={"names": "www.example.com.", "page": 1, "page_size": 50},
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
            "www",
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
def test_record_export_bind_with_long_dkim(cli: CliRunner, isolated_config: Path) -> None:
    """Regression: 2048-bit DKIM TXT records must not crash the BIND exporter."""
    long_dkim = "v=DKIM1; k=rsa; p=" + "B" * 600
    respx.get("https://my.rcodezero.at/api/v2/zones/bonsy.com/rrsets").mock(
        return_value=httpx.Response(
            200,
            json=_envelope(
                [
                    {
                        "name": "google._domainkey.bonsy.com.",
                        "type": "TXT",
                        "ttl": 3600,
                        "records": [{"content": f'"{long_dkim}"', "disabled": False}],
                    },
                ]
            ),
        ),
    )
    r = cli.invoke(app, ["--token", "tk", "record", "export", "bonsy.com"])
    assert r.exit_code == 0, r.stdout
    assert "google._domainkey" in r.stdout


def test_record_set_help_documents_upsert_semantics(cli: CliRunner) -> None:
    """`record set --help` must spell out the upsert and pre-existence flags."""
    r = cli.invoke(app, ["record", "set", "--help"])
    assert r.exit_code == 0
    assert "upsert" in r.stdout.lower()
    assert "--require-absent" in r.stdout
    assert "--require-exists" in r.stdout


def test_record_append_help_documents_merge(cli: CliRunner) -> None:
    """`record append --help` must mention fetch+merge and the race caveat."""
    r = cli.invoke(app, ["record", "append", "--help"])
    assert r.exit_code == 0
    assert "without losing" in r.stdout
    assert "last writer wins" in r.stdout


def test_record_import_help_present(cli: CliRunner) -> None:
    """`record import --help` must describe full-zone replacement."""
    r = cli.invoke(app, ["record", "import", "--help"])
    assert r.exit_code == 0
    assert "Replace every RRset" in r.stdout
    assert "--zone-file" in r.stdout


def test_record_old_verbs_are_gone(cli: CliRunner) -> None:
    """`add`, `update`, `replace-all` must no longer be registered Typer commands."""
    for verb in ("add", "update", "replace-all"):
        r = cli.invoke(app, ["record", verb, "--help"])
        assert r.exit_code != 0, f"`record {verb}` is unexpectedly still registered"


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

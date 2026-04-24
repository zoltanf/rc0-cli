"""TSIG CLI integration tests."""

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


@respx.mock
def test_tsig_list(cli: CliRunner, isolated_config: Path) -> None:
    respx.get("https://my.rcodezero.at/api/v2/tsig").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"id": 1, "name": "k1", "algorithm": "hmac-sha256", "secret": "s1"},
                {"id": 2, "name": "k2", "algorithm": "hmac-sha256", "secret": "s2"},
            ],
        ),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "tsig", "list"])
    assert r.exit_code == 0, r.stdout
    rows = json.loads(r.stdout)
    assert [row["name"] for row in rows] == ["k1", "k2"]


@respx.mock
def test_tsig_list_page_warns_when_full_page_returned(
    cli: CliRunner, isolated_config: Path
) -> None:
    """Bare-array endpoint: a full page at --page N ≥ 2 means "more may exist"."""
    rows = [{"id": i, "name": f"k{i}", "algorithm": "hmac-sha256", "secret": "s"} for i in range(3)]
    respx.get(
        "https://my.rcodezero.at/api/v2/tsig",
        params={"page": 2, "page_size": 3},
    ).mock(return_value=httpx.Response(200, json=rows))
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "-o",
            "json",
            "tsig",
            "list",
            "--page",
            "2",
            "--page-size",
            "3",
        ],
    )
    assert r.exit_code == 0, r.stdout
    assert len(json.loads(r.stdout)) == 3
    stderr = r.stderr or ""
    assert "page 2 returned a full page" in stderr
    assert "more rows may exist" in stderr


@respx.mock
def test_tsig_list_page_silent_on_short_page(cli: CliRunner, isolated_config: Path) -> None:
    """Bare-array endpoint: a short page definitely has no more data → silent."""
    rows = [
        {"id": 1, "name": "only", "algorithm": "hmac-sha256", "secret": "s"},
    ]
    respx.get(
        "https://my.rcodezero.at/api/v2/tsig",
        params={"page": 2, "page_size": 3},
    ).mock(return_value=httpx.Response(200, json=rows))
    r = cli.invoke(
        app,
        [
            "--token",
            "tk",
            "-o",
            "json",
            "tsig",
            "list",
            "--page",
            "2",
            "--page-size",
            "3",
        ],
    )
    assert r.exit_code == 0, r.stdout
    assert (r.stderr or "") == ""


@respx.mock
def test_tsig_show(cli: CliRunner, isolated_config: Path) -> None:
    respx.get("https://my.rcodezero.at/api/v2/tsig/xfr").mock(
        return_value=httpx.Response(
            200,
            json={"name": "xfr", "algorithm": "hmac-sha256", "secret": "s"},
        ),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "tsig", "show", "xfr"])
    assert r.exit_code == 0, r.stdout
    assert json.loads(r.stdout)["name"] == "xfr"


@respx.mock
def test_tsig_list_out_emits_deprecation_warning(
    cli: CliRunner,
    isolated_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RC0_SUPPRESS_DEPRECATED", raising=False)
    respx.get("https://my.rcodezero.at/api/v2/tsig/out").mock(
        return_value=httpx.Response(
            200,
            json={"name": "legacy", "algorithm": "hmac-md5", "secret": "old", "default_key": True},
        ),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "tsig", "list-out"])
    assert r.exit_code == 0, r.stdout
    assert json.loads(r.stdout)["name"] == "legacy"
    # CliRunner splits stderr on Click 8.2+ — stderr is where the warning lands.
    assert "[DEPRECATED]" in (r.stderr or "") or "[DEPRECATED]" in r.stdout


@respx.mock
def test_tsig_list_out_suppressed_by_env(
    cli: CliRunner,
    isolated_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RC0_SUPPRESS_DEPRECATED", "1")
    respx.get("https://my.rcodezero.at/api/v2/tsig/out").mock(
        return_value=httpx.Response(
            200,
            json={"name": "legacy", "algorithm": "hmac-md5", "secret": "old"},
        ),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "tsig", "list-out"])
    assert r.exit_code == 0, r.stdout
    assert "[DEPRECATED]" not in (r.stderr or "")

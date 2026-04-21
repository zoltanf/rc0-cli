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

"""Settings CLI integration tests."""

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
def test_settings_show(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.get("https://my.rcodezero.at/api/v2/settings").mock(
        return_value=httpx.Response(
            200,
            json={
                "secondaries": ["ns1.example.", "ns2.example."],
                "tsigin": "in-key",
                "tsigout": "out-key",
            },
        ),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "settings", "show"])
    assert r.exit_code == 0, r.stdout
    assert route.called
    body = json.loads(r.stdout)
    assert body["tsigin"] == "in-key"
    assert body["tsigout"] == "out-key"
    assert body["secondaries"] == ["ns1.example.", "ns2.example."]

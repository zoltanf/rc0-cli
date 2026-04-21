"""Messages CLI integration tests."""

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
    current_page: int,
    last_page: int,
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
def test_messages_poll_single(cli: CliRunner, isolated_config: Path) -> None:
    respx.get("https://my.rcodezero.at/api/v2/messages").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 7,
                "domain": "x",
                "date": "2026-04-21T00:00:00Z",
                "type": "DSSEEN",
                "comment": "hello",
            },
        ),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "messages", "poll"])
    assert r.exit_code == 0, r.stdout
    assert json.loads(r.stdout)["id"] == 7


@respx.mock
def test_messages_poll_empty(cli: CliRunner, isolated_config: Path) -> None:
    respx.get("https://my.rcodezero.at/api/v2/messages").mock(
        return_value=httpx.Response(200, json={}),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "messages", "poll"])
    assert r.exit_code == 0, r.stdout
    assert json.loads(r.stdout) == {}


@respx.mock
def test_messages_list_pages(cli: CliRunner, isolated_config: Path) -> None:
    respx.get("https://my.rcodezero.at/api/v2/messages/list").mock(
        return_value=httpx.Response(
            200,
            json=_envelope(
                [
                    {
                        "id": 1,
                        "domain": "a.example.",
                        "date": "2026-04-20T00:00:00Z",
                        "type": "DSSEEN",
                        "comment": "m1",
                    },
                    {
                        "id": 2,
                        "domain": "b.example.",
                        "date": "2026-04-21T00:00:00Z",
                        "type": "DSSEEN",
                        "comment": "m2",
                    },
                ],
                current_page=1,
                last_page=1,
            ),
        ),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "messages", "list"])
    assert r.exit_code == 0, r.stdout
    assert [m["id"] for m in json.loads(r.stdout)] == [1, 2]

"""Messages write-command integration tests."""

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
def test_messages_ack_live(cli: CliRunner, isolated_config: Path) -> None:
    route = respx.delete("https://my.rcodezero.at/api/v2/messages/7").mock(
        return_value=httpx.Response(204),
    )
    r = cli.invoke(app, ["--token", "tk", "-o", "json", "messages", "ack", "7"])
    assert r.exit_code == 0, r.stdout
    assert route.called


def test_messages_ack_dry_run(cli: CliRunner, isolated_config: Path) -> None:
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json", "--dry-run", "messages", "ack", "7"],
    )
    assert r.exit_code == 0, r.stdout
    parsed = json.loads(r.stdout)
    assert parsed["dry_run"] is True
    assert parsed["request"]["method"] == "DELETE"
    assert parsed["request"]["url"].endswith("/api/v2/messages/7")


@respx.mock
def test_messages_ack_all_loops_until_empty(
    cli: CliRunner,
    isolated_config: Path,
) -> None:
    poll = respx.get("https://my.rcodezero.at/api/v2/messages")
    poll.side_effect = [
        httpx.Response(200, json={"id": 1, "domain": "a", "date": "d", "type": "t"}),
        httpx.Response(200, json={"id": 2, "domain": "b", "date": "d", "type": "t"}),
        httpx.Response(200, json={}),
    ]
    del1 = respx.delete("https://my.rcodezero.at/api/v2/messages/1").mock(
        return_value=httpx.Response(204),
    )
    del2 = respx.delete("https://my.rcodezero.at/api/v2/messages/2").mock(
        return_value=httpx.Response(204),
    )
    r = cli.invoke(
        app,
        ["--token", "tk", "-y", "-o", "json", "messages", "ack-all"],
    )
    assert r.exit_code == 0, r.stdout
    assert del1.called and del2.called
    payload = json.loads(r.stdout)
    assert payload["acknowledged"] == [1, 2]


def test_messages_ack_all_yn_declined(
    cli: CliRunner,
    isolated_config: Path,
) -> None:
    r = cli.invoke(
        app,
        ["--token", "tk", "messages", "ack-all"],
        input="n\n",
    )
    assert r.exit_code == 12, r.stdout


def test_messages_ack_all_dry_run_emits_single_summary(
    cli: CliRunner,
    isolated_config: Path,
) -> None:
    r = cli.invoke(
        app,
        ["--token", "tk", "-o", "json", "--dry-run", "messages", "ack-all"],
    )
    assert r.exit_code == 0, r.stdout
    payload = json.loads(r.stdout)
    assert payload["dry_run"] is True
    assert payload["summary"].lower().startswith("would acknowledge")

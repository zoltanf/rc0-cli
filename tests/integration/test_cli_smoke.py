"""CLI smoke tests using Typer's CliRunner."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from rc0 import __version__ as rc0_version
from rc0.app import app

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def cli() -> CliRunner:
    return CliRunner()


def test_version_flag(cli: CliRunner) -> None:
    r = cli.invoke(app, ["--version"])
    assert r.exit_code == 0
    assert rc0_version in r.stdout


def test_version_command_json(cli: CliRunner, isolated_config: Path) -> None:
    r = cli.invoke(app, ["--output", "json", "version"])
    assert r.exit_code == 0
    parsed = json.loads(r.stdout)
    assert parsed["version"] == rc0_version


def test_help_shows_command_groups(cli: CliRunner) -> None:
    r = cli.invoke(app, ["--help"])
    assert r.exit_code == 0
    for group in (
        "auth",
        "config",
        "help",
        "introspect",
        "messages",
        "record",
        "report",
        "settings",
        "stats",
        "tsig",
        "version",
        "zone",
    ):
        assert group in r.stdout, f"{group!r} missing from --help"


def test_config_show_json(cli: CliRunner, isolated_config: Path) -> None:
    r = cli.invoke(app, ["--output", "json", "config", "show"])
    assert r.exit_code == 0
    parsed = json.loads(r.stdout)
    assert parsed["profile"] == "default"
    assert parsed["api_url"].startswith("https://")


def test_config_set_get_round_trip(cli: CliRunner, isolated_config: Path) -> None:
    r = cli.invoke(app, ["config", "set", "timeout", "45"])
    assert r.exit_code == 0
    r = cli.invoke(app, ["--output", "json", "config", "get", "timeout"])
    assert r.exit_code == 0
    parsed = json.loads(r.stdout)
    assert parsed["timeout"] == 45.0


def test_help_topic_authentication(cli: CliRunner, isolated_config: Path) -> None:
    r = cli.invoke(app, ["help", "authentication"])
    assert r.exit_code == 0
    assert "Authentication" in r.stdout
    assert "rc0 auth login" in r.stdout


def test_help_topic_unknown_is_not_found(cli: CliRunner, isolated_config: Path) -> None:
    r = cli.invoke(app, ["help", "does-not-exist"])
    assert r.exit_code == 6  # NotFoundError


def test_help_topic_pagination(cli: CliRunner, isolated_config: Path) -> None:
    r = cli.invoke(app, ["help", "pagination"])
    assert r.exit_code == 0
    assert "Pagination" in r.stdout
    assert "--all" in r.stdout


def test_help_topic_profiles_and_config(cli: CliRunner, isolated_config: Path) -> None:
    r = cli.invoke(app, ["help", "profiles-and-config"])
    assert r.exit_code == 0
    assert "Profiles" in r.stdout
    assert "RC0_PROFILE" in r.stdout

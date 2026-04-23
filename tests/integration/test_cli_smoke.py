"""CLI smoke tests using Typer's CliRunner."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rc0 import __version__ as rc0_version
from rc0.app import app


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


# regression: Bug 1 — help list must succeed and enumerate real topic names
def test_help_list_returns_topics(cli: CliRunner, isolated_config: Path) -> None:
    r = cli.invoke(app, ["help", "list"])
    assert r.exit_code == 0, r.stdout
    lines = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
    assert "authentication" in lines
    assert "pagination" in lines
    assert "output-formats" in lines


# regression: Bug 4 — zone list --help must show -o before the subcommand
def test_zone_list_help_uses_correct_output_flag_position(
    cli: CliRunner,
    isolated_config: Path,
) -> None:
    r = cli.invoke(app, ["zone", "list", "--help"])
    assert r.exit_code == 0, r.stdout
    assert "zone list -o json" not in r.stdout, (
        "example places -o after subcommand; it must come before: rc0 -o json zone list"
    )


def test_main_entrypoint_hoists_argv(tmp_path: Path) -> None:
    """End-to-end: invoking ``python -m rc0`` must hoist post-subcommand flags."""
    env = {
        **os.environ,
        "XDG_CONFIG_HOME": str(tmp_path),
        "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src"),
    }
    env.pop("RC0_CONFIG", None)
    env.pop("RC0_API_TOKEN", None)
    r = subprocess.run(
        [sys.executable, "-m", "rc0", "config", "show", "-o", "json"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert r.returncode == 0, f"stderr={r.stderr}\nstdout={r.stdout}"
    parsed = json.loads(r.stdout)
    assert parsed["profile"] == "default"

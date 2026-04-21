"""`rc0 introspect` emits the documented JSON schema."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from rc0.app import app


def test_introspect_emits_documented_schema() -> None:
    r = CliRunner().invoke(app, ["introspect"])
    assert r.exit_code == 0, r.stdout
    data = json.loads(r.stdout)
    assert "rc0_version" in data
    assert isinstance(data["commands"], list)
    paths = {tuple(c["path"]) for c in data["commands"]}
    assert ("zone", "list") in paths
    assert ("record", "export") in paths
    assert ("introspect",) in paths


def test_introspect_flags_deprecated_commands() -> None:
    r = CliRunner().invoke(app, ["introspect"])
    assert r.exit_code == 0, r.stdout
    data = json.loads(r.stdout)
    topmag = next(c for c in data["commands"] if c["path"] == ["stats", "topmagnitude"])
    assert topmag["hidden"] is True
    assert topmag["deprecated"] is True


def test_introspect_live_commands_not_deprecated() -> None:
    r = CliRunner().invoke(app, ["introspect"])
    assert r.exit_code == 0, r.stdout
    data = json.loads(r.stdout)
    zone_list = next(c for c in data["commands"] if c["path"] == ["zone", "list"])
    assert zone_list["hidden"] is False
    assert zone_list["deprecated"] is False

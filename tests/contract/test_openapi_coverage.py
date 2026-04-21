"""Every non-deprecated v2 GET in the pinned spec has a CLI command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from rc0.app import app
from tests.contract._expected_v2_gets import PHASE_2_OR_LATER, V2_GET_TO_COMMAND

SPEC_PATH = Path(__file__).parent.parent / "fixtures" / "openapi.json"


def _load_v2_gets() -> list[str]:
    """Return every v2 path that has a `get` method in the pinned spec."""
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    paths: list[str] = []
    for path, methods in spec["paths"].items():
        if not path.startswith("/api/v2/"):
            continue
        if "get" in methods:
            paths.append(path)
    return sorted(paths)


def test_every_v2_get_is_mapped() -> None:
    """Exhaustiveness — no v2 GET in the spec is missing from the table."""
    spec_paths = set(_load_v2_gets())
    mapped = set(V2_GET_TO_COMMAND)
    missing = spec_paths - mapped
    assert not missing, (
        f"v2 GET endpoints without a CLI mapping in "
        f"tests/contract/_expected_v2_gets.py: {sorted(missing)}"
    )


@pytest.mark.parametrize(
    ("path", "command_path"),
    sorted((p, cmd) for p, cmd in V2_GET_TO_COMMAND.items() if p not in PHASE_2_OR_LATER),
    ids=lambda v: " ".join(v) if isinstance(v, tuple) else v,
)
def test_command_exists_for_path(
    path: str,
    command_path: tuple[str, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each mapped command must exist — its `--help` must exit 0.

    Suppress the deprecation warning in the env so --help output for hidden
    commands stays clean.
    """
    monkeypatch.setenv("RC0_SUPPRESS_DEPRECATED", "1")
    args = [*command_path, "--help"]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, (
        f"`rc0 {' '.join(command_path)} --help` failed (exit {result.exit_code}) "
        f"for spec path {path}:\n{result.output}"
    )

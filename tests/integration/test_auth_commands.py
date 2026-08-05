"""Auth CLI integration tests — token hygiene and the unexpected-error guard."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest
import respx
from typer.testing import CliRunner

from rc0.app import _run, app

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def cli() -> CliRunner:
    return CliRunner()


@pytest.mark.parametrize("value", [" ", "   ", "\t"])
def test_login_with_blank_token_is_a_clean_config_error(
    cli: CliRunner,
    isolated_config: Path,
    value: str,
) -> None:
    r = cli.invoke(app, ["auth", "login", "--token-value", value])
    assert r.exit_code == 3
    assert "No token provided." in r.output
    assert "Traceback" not in r.output


def test_login_with_embedded_space_is_a_clean_config_error(
    cli: CliRunner,
    isolated_config: Path,
) -> None:
    r = cli.invoke(app, ["auth", "login", "--token-value", "tk with space"])
    assert r.exit_code == 3
    assert "not valid in an HTTP header" in r.output
    assert "Traceback" not in r.output


@respx.mock
def test_login_strips_surrounding_whitespace_before_storing(
    cli: CliRunner,
    isolated_config: Path,
) -> None:
    route = respx.get("https://my.rcodezero.at/api/v2/zones").mock(
        return_value=httpx.Response(200, json={"data": []}),
    )
    r = cli.invoke(app, ["auth", "login", "--token-value", "  tk1234\n"])
    assert r.exit_code == 0, r.output
    assert route.calls[0].request.headers["Authorization"] == "Bearer tk1234"

    from rc0 import auth as auth_core

    record = auth_core.load_token("default")
    assert record is not None
    assert auth_core.token_of(record) == "tk1234"


def test_unexpected_exception_is_reported_without_a_traceback(
    isolated_config: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("kaboom")

    monkeypatch.setattr("rc0.app.load_profile", _boom)
    rc = _run(["version"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "error: unexpected RuntimeError: kaboom" in err
    assert "please report it" in err

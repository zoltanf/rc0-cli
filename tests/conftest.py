"""Shared pytest fixtures."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point rc0's config loader at a tmp dir so tests don't touch the user's real config."""
    cfg_dir = tmp_path / "rc0"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("RC0_CONFIG_DIR", str(cfg_dir))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("RC0_CONFIG", raising=False)
    monkeypatch.delenv("RC0_API_TOKEN", raising=False)
    yield cfg_dir


class _InMemoryKeyring:
    """Minimal keyring stand-in: in-memory dict, cross-platform, no real OS calls.

    Exposes the three functions rc0.auth uses. Each test gets a fresh store
    via the ``_fake_keyring`` fixture.
    """

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], str] = {}

    def set_password(self, service: str, user: str, password: str) -> None:
        self._store[(service, user)] = password

    def get_password(self, service: str, user: str) -> str | None:
        return self._store.get((service, user))

    def delete_password(self, service: str, user: str) -> None:
        if (service, user) not in self._store:
            raise KeyError((service, user))
        del self._store[(service, user)]


@pytest.fixture(autouse=True)
def _fake_keyring() -> Iterator[_InMemoryKeyring]:
    """Swap in an in-memory keyring so tests exercise the keyring code path.

    Without this, tests would either hit the real OS keyring (flaky, leaves
    state) or the file fallback (which is refused on Windows by design).
    """
    fake = _InMemoryKeyring()
    previous = sys.modules.get("keyring")
    sys.modules["keyring"] = fake  # type: ignore[assignment]
    try:
        yield fake
    finally:
        if previous is None:
            sys.modules.pop("keyring", None)
        else:
            sys.modules["keyring"] = previous

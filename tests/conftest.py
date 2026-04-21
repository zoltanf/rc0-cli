"""Shared pytest fixtures."""

from __future__ import annotations

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


@pytest.fixture(autouse=True)
def _no_real_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent tests from accidentally hitting the real OS keyring.

    Forces the file-fallback path by making the keyring module look unimportable
    to ``rc0.auth._keyring_module``.
    """
    import sys

    # If keyring is already imported (from another test), mask it.
    sys.modules["keyring"] = None  # type: ignore[assignment]
    yield
    sys.modules.pop("keyring", None)

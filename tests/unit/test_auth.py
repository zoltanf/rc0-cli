"""Token storage tests — file-fallback path (keyring masked in conftest)."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

from rc0 import auth

if TYPE_CHECKING:
    from pathlib import Path


def test_store_and_load_via_file(isolated_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if sys.platform == "win32":
        pytest.skip("File fallback is refused on Windows.")
    record = auth.store_token("default", "abcd1234", prefer_keyring=False)
    assert record.backend == "file"
    assert record.tail == "1234"

    loaded = auth.load_token("default")
    assert loaded is not None
    assert loaded.backend == "file"
    assert auth.token_of(loaded) == "abcd1234"


def test_env_var_takes_precedence(isolated_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if sys.platform != "win32":
        auth.store_token("default", "fileonly", prefer_keyring=False)
    monkeypatch.setenv("RC0_API_TOKEN", "fromenv")
    record = auth.load_token("default")
    assert record is not None
    assert record.backend == "env"
    assert auth.token_of(record) == "fromenv"


def test_delete_removes_file_token(isolated_config: Path) -> None:
    if sys.platform == "win32":
        pytest.skip("File fallback is refused on Windows.")
    auth.store_token("default", "xyz987", prefer_keyring=False)
    assert auth.delete_token("default") is True
    assert auth.load_token("default") is None


def test_empty_token_rejected(isolated_config: Path) -> None:
    from rc0.client.errors import ConfigError

    with pytest.raises(ConfigError, match="empty"):
        auth.store_token("default", "", prefer_keyring=False)

"""Token storage tests — covers the keyring, file-fallback, and env paths."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

from rc0 import auth

if TYPE_CHECKING:
    from pathlib import Path


def test_store_and_load_via_keyring(isolated_config: Path) -> None:
    record = auth.store_token("default", "kr-1234", prefer_keyring=True)
    assert record.backend == "keyring"
    assert record.tail == "1234"

    loaded = auth.load_token("default")
    assert loaded is not None
    assert loaded.backend == "keyring"
    assert auth.token_of(loaded) == "kr-1234"


def test_store_and_load_via_file(isolated_config: Path) -> None:
    if sys.platform == "win32":
        pytest.skip("File fallback is refused on Windows.")
    record = auth.store_token("default", "abcd1234", prefer_keyring=False)
    assert record.backend == "file"

    loaded = auth.load_token("default")
    assert loaded is not None
    assert loaded.backend == "file"
    assert auth.token_of(loaded) == "abcd1234"


def test_env_var_takes_precedence(
    isolated_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Pre-seed the keyring so we can confirm env wins over it.
    auth.store_token("default", "storedtoken", prefer_keyring=True)
    monkeypatch.setenv("RC0_API_TOKEN", "fromenv")
    record = auth.load_token("default")
    assert record is not None
    assert record.backend == "env"
    assert auth.token_of(record) == "fromenv"


def test_delete_removes_keyring_token(isolated_config: Path) -> None:
    auth.store_token("default", "xyz987", prefer_keyring=True)
    assert auth.delete_token("default") is True
    assert auth.load_token("default") is None


def test_delete_returns_false_when_nothing_stored(isolated_config: Path) -> None:
    assert auth.delete_token("nonexistent") is False


def test_empty_token_rejected(isolated_config: Path) -> None:
    from rc0.client.errors import ConfigError

    with pytest.raises(ConfigError, match="empty"):
        auth.store_token("default", "", prefer_keyring=True)


def test_file_fallback_used_when_keyring_set_fails(
    isolated_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If keyring raises, we should try the file path (non-Windows only)."""
    if sys.platform == "win32":
        pytest.skip("File fallback is refused on Windows.")

    def _broken_set(*args: object, **kwargs: object) -> None:
        msg = "keyring broken"
        raise RuntimeError(msg)

    monkeypatch.setattr("sys.modules", sys.modules.copy())
    fake = sys.modules["keyring"]
    monkeypatch.setattr(fake, "set_password", _broken_set, raising=True)

    record = auth.store_token("default", "fallback-token", prefer_keyring=True)
    assert record.backend == "file"

"""Token storage: OS keyring preferred, 0600 credentials file as fallback.

Mission plan §8:

* Prefer keyring (macOS Keychain / Windows Credential Manager / Secret Service).
* Fallback to ``$XDG_CONFIG_HOME/rc0/credentials`` with mode 0600.
* Never log tokens, never print them, redact them in any HTTP trace output.
"""

from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import tomli_w

from rc0.client.errors import ConfigError
from rc0.config import config_dir

if TYPE_CHECKING:
    from pathlib import Path

KEYRING_SERVICE = "rc0-cli"


@dataclass(frozen=True)
class TokenRecord:
    """Where a token is stored, so ``auth status`` can report it honestly."""

    profile: str
    backend: str  # "keyring" | "file" | "env"
    tail: str  # last 4 chars for display only


def credentials_path() -> Path:
    return config_dir() / "credentials"


# --------------------------------------------------------------------- public


def store_token(profile: str, token: str, *, prefer_keyring: bool = True) -> TokenRecord:
    """Persist ``token`` for ``profile``. Keyring first, file fallback."""
    if not token:
        raise ConfigError("Refusing to store an empty token.")
    if prefer_keyring and _try_keyring_set(profile, token):
        return TokenRecord(profile=profile, backend="keyring", tail=_tail(token))
    _file_set(profile, token)
    return TokenRecord(profile=profile, backend="file", tail=_tail(token))


def load_token(profile: str) -> TokenRecord | None:
    """Return the stored token for ``profile``, or ``None`` if missing.

    Environment variable ``RC0_API_TOKEN`` always wins; it's the highest-precedence
    source per mission plan §6.
    """
    env_token = os.environ.get("RC0_API_TOKEN")
    if env_token:
        record = TokenRecord(profile=profile, backend="env", tail=_tail(env_token))
        return _with_token(record, env_token)

    keyring_token = _try_keyring_get(profile)
    if keyring_token is not None:
        return _with_token(
            TokenRecord(profile=profile, backend="keyring", tail=_tail(keyring_token)),
            keyring_token,
        )

    file_token = _file_get(profile)
    if file_token is not None:
        return _with_token(
            TokenRecord(profile=profile, backend="file", tail=_tail(file_token)),
            file_token,
        )
    return None


def delete_token(profile: str) -> bool:
    """Remove ``profile``'s token from every backend. True if any backend had it."""
    removed = False
    if _try_keyring_delete(profile):
        removed = True
    if _file_delete(profile):
        removed = True
    return removed


# Tokens returned by load_token() carry a private attribute; callers use
# `record.token` after import via this helper to keep type-checkers happy.
def token_of(record: TokenRecord) -> str:
    """Return the raw token value from a record produced by :func:`load_token`."""
    value: str = getattr(record, "_token", "")
    return value


def _with_token(record: TokenRecord, token: str) -> TokenRecord:
    # Frozen dataclass — stash via object.__setattr__.
    object.__setattr__(record, "_token", token)
    return record


def _tail(token: str, n: int = 4) -> str:
    return token[-n:] if len(token) >= n else token


# --------------------------------------------------------------------- keyring


def _keyring_module() -> Any | None:
    try:
        import keyring
    except ImportError:
        return None
    return keyring


def _try_keyring_set(profile: str, token: str) -> bool:
    kr = _keyring_module()
    if kr is None:
        return False
    try:
        kr.set_password(KEYRING_SERVICE, profile, token)
    except Exception:
        return False
    return True


def _try_keyring_get(profile: str) -> str | None:
    kr = _keyring_module()
    if kr is None:
        return None
    try:
        value = kr.get_password(KEYRING_SERVICE, profile)
    except Exception:
        return None
    return value if isinstance(value, str) else None


def _try_keyring_delete(profile: str) -> bool:
    kr = _keyring_module()
    if kr is None:
        return False
    try:
        kr.delete_password(KEYRING_SERVICE, profile)
    except Exception:
        return False
    return True


# ------------------------------------------------------------------------ file


def _file_load() -> dict[str, Any]:
    path = credentials_path()
    if not path.exists():
        return {}
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        msg = f"Failed to read credentials at {path}: {exc}"
        raise ConfigError(msg) from exc


def _file_save(data: dict[str, Any]) -> None:
    path = credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(tomli_w.dumps(data).encode("utf-8"))
    if sys.platform != "win32":
        os.chmod(tmp, 0o600)  # noqa: PTH101
    tmp.replace(path)
    if sys.platform != "win32":
        os.chmod(path, 0o600)  # noqa: PTH101


def _file_set(profile: str, token: str) -> None:
    if sys.platform == "win32":
        msg = (
            "Keyring unavailable and file-fallback refuses to write plaintext on Windows. "
            "Install the `keyring` backend (Windows Credential Manager) and retry."
        )
        raise ConfigError(msg)
    data = _file_load()
    profiles = data.setdefault("profiles", {})
    profiles[profile] = {"token": token}
    _file_save(data)


def _file_get(profile: str) -> str | None:
    data = _file_load()
    profiles = data.get("profiles")
    if not isinstance(profiles, dict):
        return None
    entry = profiles.get(profile)
    if not isinstance(entry, dict):
        return None
    token = entry.get("token")
    return str(token) if isinstance(token, str) else None


def _file_delete(profile: str) -> bool:
    data = _file_load()
    profiles = data.get("profiles")
    if not isinstance(profiles, dict) or profile not in profiles:
        return False
    del profiles[profile]
    _file_save(data)
    return True

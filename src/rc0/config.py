"""Config model and layered loader.

Precedence (mission plan §6): CLI flag > env var > profile in config file >
global default.

The config file format is TOML (mission plan §8.2). Tokens are **never**
written to the config file — they live in the OS keyring or the
``credentials`` file under mode 0600 (see :mod:`rc0.auth`).
"""

from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomli_w

from rc0.client.errors import ConfigError


@dataclass
class ProfileConfig:
    """Effective config for one profile, after layering defaults and file."""

    api_url: str = "https://my.rcodezero.at"
    output: str = "table"
    timeout: float = 30.0
    retries: int = 3

    def merge(self, other: dict[str, Any]) -> ProfileConfig:
        return ProfileConfig(
            api_url=str(other.get("api_url", self.api_url)),
            output=str(other.get("output", self.output)),
            timeout=float(other.get("timeout", self.timeout)),
            retries=int(other.get("retries", self.retries)),
        )


# --------------------------------------------------------------------- paths


def config_dir() -> Path:
    """Return the directory that holds ``config.toml`` and ``credentials``."""
    override = os.environ.get("RC0_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "rc0"
        return Path.home() / "AppData" / "Roaming" / "rc0"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "rc0"
    return Path.home() / ".config" / "rc0"


def config_path() -> Path:
    """Return the effective path to ``config.toml``."""
    override = os.environ.get("RC0_CONFIG")
    if override:
        return Path(override).expanduser()
    return config_dir() / "config.toml"


# ------------------------------------------------------------------- reading


def load_toml(path: Path | None = None) -> dict[str, Any]:
    """Load raw TOML from ``path`` (or the resolved default)."""
    cfg = path or config_path()
    if not cfg.exists():
        return {}
    try:
        with cfg.open("rb") as fh:
            return tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        msg = f"Failed to read config at {cfg}: {exc}"
        raise ConfigError(msg, hint="Run `rc0 config path` and inspect the file.") from exc


def load_profile(name: str = "default", *, path: Path | None = None) -> ProfileConfig:
    """Return the merged :class:`ProfileConfig` for profile ``name``.

    Falls back to the ``[default]`` table for keys missing in the named profile.
    """
    raw = load_toml(path)
    defaults: dict[str, Any] = {}
    if isinstance(raw.get("default"), dict):
        defaults = {k: v for k, v in raw["default"].items() if not isinstance(v, dict)}
    profiles = raw.get("profiles") if isinstance(raw.get("profiles"), dict) else {}
    profile_values = profiles.get(name, {}) if isinstance(profiles, dict) else {}
    merged = {**defaults, **(profile_values if isinstance(profile_values, dict) else {})}
    return ProfileConfig().merge(merged)


# ------------------------------------------------------------------- writing


def ensure_config_dir() -> Path:
    """Create the config directory if missing; return its path."""
    d = config_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_toml(data: dict[str, Any], *, path: Path | None = None) -> Path:
    """Write ``data`` to the config file, creating parent dirs as needed."""
    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_bytes(tomli_w.dumps(data).encode("utf-8"))
    tmp.replace(target)
    return target


ALLOWED_KEYS: frozenset[str] = frozenset({"api_url", "output", "timeout", "retries"})


def set_value(key: str, value: str, *, profile: str = "default", path: Path | None = None) -> Path:
    """Set one key in ``profile`` and persist."""
    if key not in ALLOWED_KEYS:
        msg = f"Unknown config key '{key}'. Allowed: {', '.join(sorted(ALLOWED_KEYS))}."
        raise ConfigError(msg)
    data = load_toml(path)
    coerced: Any = value
    if key == "timeout":
        coerced = _coerce_float(key, value)
    elif key == "retries":
        coerced = _coerce_int(key, value)

    if profile == "default":
        section = data.setdefault("default", {})
    else:
        profiles = data.setdefault("profiles", {})
        section = profiles.setdefault(profile, {})
    section[key] = coerced
    return write_toml(data, path=path)


def unset_value(key: str, *, profile: str = "default", path: Path | None = None) -> Path:
    """Remove one key from ``profile`` and persist."""
    data = load_toml(path)
    section = data.get("default" if profile == "default" else "profiles", {})
    if profile != "default" and isinstance(section, dict):
        section = section.get(profile, {})
    if isinstance(section, dict) and key in section:
        del section[key]
    return write_toml(data, path=path)


def _coerce_float(key: str, value: str) -> float:
    try:
        return float(value)
    except ValueError as exc:
        msg = f"Config key '{key}' expects a number, got {value!r}."
        raise ConfigError(msg) from exc


def _coerce_int(key: str, value: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        msg = f"Config key '{key}' expects an integer, got {value!r}."
        raise ConfigError(msg) from exc

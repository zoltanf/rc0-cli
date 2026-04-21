"""Config file loader / setter tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from rc0.client.errors import ConfigError
from rc0.config import (
    ProfileConfig,
    load_profile,
    load_toml,
    set_value,
    unset_value,
    write_toml,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_load_profile_with_no_file(isolated_config: Path) -> None:
    cfg = load_profile("default")
    assert cfg == ProfileConfig()


def test_profile_inherits_from_default(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    write_toml(
        {
            "default": {"api_url": "https://prod.example", "timeout": 10.0},
            "profiles": {"test": {"api_url": "https://test.example"}},
        },
        path=path,
    )
    cfg = load_profile("test", path=path)
    assert cfg.api_url == "https://test.example"
    assert cfg.timeout == 10.0  # inherited from [default]


def test_set_and_unset_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    set_value("api_url", "https://x.example", path=path)
    set_value("timeout", "12.5", path=path)
    data = load_toml(path)
    assert data["default"]["api_url"] == "https://x.example"
    assert data["default"]["timeout"] == 12.5
    unset_value("timeout", path=path)
    assert "timeout" not in load_toml(path)["default"]


def test_set_rejects_unknown_key(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    with pytest.raises(ConfigError, match="Unknown config key"):
        set_value("nope", "value", path=path)


def test_set_coerces_numeric_types(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    set_value("retries", "5", path=path)
    assert load_toml(path)["default"]["retries"] == 5
    with pytest.raises(ConfigError, match="expects an integer"):
        set_value("retries", "not-a-number", path=path)

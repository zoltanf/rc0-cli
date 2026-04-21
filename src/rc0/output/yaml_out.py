"""YAML output — block style via PyYAML, no ANSI."""

from __future__ import annotations

from typing import Any

import yaml


def render(data: Any) -> str:
    return yaml.safe_dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)

"""JSON output — always valid JSON, no ANSI, deterministic ordering."""

from __future__ import annotations

import json
from typing import Any


def render(data: Any, *, compact: bool = False) -> str:
    if compact:
        return json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    return json.dumps(data, indent=2, ensure_ascii=False)

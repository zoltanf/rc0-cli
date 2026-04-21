"""Plain output — bare text, one record per line, space-separated fields."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence


def render(data: Any, *, columns: Sequence[str] | None = None) -> str:
    if isinstance(data, dict):
        items: list[dict[str, Any]] = [data]
    elif isinstance(data, list):
        items = [x for x in data if isinstance(x, dict)]
        # If it's a flat list of scalars, one per line.
        if not items and data:
            return "\n".join(_scalar(x) for x in data)
    elif data is None:
        return ""
    else:
        return _scalar(data)

    lines: list[str] = []
    for item in items:
        keys = list(columns) if columns else list(item.keys())
        lines.append(" ".join(_scalar(item.get(k)) for k in keys))
    return "\n".join(lines)


def _scalar(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)

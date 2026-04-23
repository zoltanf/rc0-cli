"""Shared value-to-string conversion for output formatters."""

from __future__ import annotations

from typing import Any


def stringify(value: Any, *, list_sep: str = ", ") -> str:
    """Convert a field value to a display string.

    None → empty string; bool → lowercase literal; list/tuple → joined with
    list_sep; dict → key=value pairs joined with list_sep; anything else → str().
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list | tuple):
        return list_sep.join(stringify(v, list_sep=list_sep) for v in value)
    if isinstance(value, dict):
        return list_sep.join(f"{k}={stringify(v, list_sep=list_sep)}" for k, v in value.items())
    return str(value)

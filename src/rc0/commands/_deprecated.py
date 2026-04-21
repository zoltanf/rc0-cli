"""Helper for deprecated commands — warn on stderr and keep it off default --help."""

from __future__ import annotations

import os
import sys

_TRUTHY_VALUES = frozenset({"1", "true", "yes", "on"})


def deprecated_warn(command: str) -> None:
    """Print a ``[DEPRECATED]`` banner for ``command`` unless suppressed.

    Set ``RC0_SUPPRESS_DEPRECATED`` to one of ``1``/``true``/``yes``/``on``
    (case-insensitive) to silence this warning in scripts that knowingly
    exercise deprecated endpoints (e.g. the contract test). Any other value
    — including ``0`` and ``false`` — leaves the warning enabled.
    """
    if os.environ.get("RC0_SUPPRESS_DEPRECATED", "").lower() in _TRUTHY_VALUES:
        return
    sys.stderr.write(f"[DEPRECATED] {command} calls a deprecated endpoint.\n")

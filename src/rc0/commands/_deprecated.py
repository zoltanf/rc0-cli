"""Helper for deprecated commands — warn on stderr and keep it off default --help."""

from __future__ import annotations

import os
import sys


def deprecated_warn(command: str) -> None:
    """Print a ``[DEPRECATED]`` banner for ``command`` unless suppressed.

    Set ``RC0_SUPPRESS_DEPRECATED=1`` to silence in scripts that knowingly
    exercise deprecated endpoints (e.g. the contract test).
    """
    if os.environ.get("RC0_SUPPRESS_DEPRECATED"):
        return
    sys.stderr.write(f"[DEPRECATED] {command} calls a deprecated endpoint.\n")

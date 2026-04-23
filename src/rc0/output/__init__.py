"""Output formatters for rc0.

The dispatcher :func:`render` takes data plus an :class:`OutputFormat` and
writes to the given stream. Individual modules implement each format.

Rules (mission plan §9):

* Machine output never writes to stderr unless it's an error.
* No ANSI codes in non-table formats, ever (even on a TTY).
* JSON arrays are ordered by a documented key (commonly ``domain`` or ``id``).
"""

from __future__ import annotations

import sys
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence


class OutputFormat(StrEnum):
    table = "table"
    json = "json"
    yaml = "yaml"
    csv = "csv"
    tsv = "tsv"
    plain = "plain"


def stdout_is_tty() -> bool:
    return bool(getattr(sys.stdout, "isatty", lambda: False)())


def resolve_default(fmt: OutputFormat) -> OutputFormat:
    """Fall table back to plain when stdout is not a TTY (§9)."""
    if fmt is OutputFormat.table and not stdout_is_tty():
        return OutputFormat.plain
    return fmt


def render(
    data: Any,
    *,
    fmt: OutputFormat | str = OutputFormat.table,
    columns: Sequence[str] | None = None,
    title: str | None = None,
    compact: bool = False,
) -> str:
    """Render ``data`` as a string in ``fmt``.

    ``columns`` is used by table/csv/tsv/plain to select and order keys from
    a list of dicts. JSON and YAML ignore it.
    """
    try:
        coerced = OutputFormat(fmt)
    except ValueError as exc:
        msg = f"Unknown output format: {fmt}"
        raise ValueError(msg) from exc
    effective = resolve_default(coerced)
    match effective:
        case OutputFormat.table:
            from rc0.output import table

            return table.render(data, columns=columns, title=title)
        case OutputFormat.json:
            from rc0.output import json_out

            return json_out.render(data, compact=compact)
        case OutputFormat.yaml:
            from rc0.output import yaml_out

            return yaml_out.render(data)
        case OutputFormat.csv:
            from rc0.output import csv_tsv

            return csv_tsv.render(data, columns=columns, delimiter=",")
        case OutputFormat.tsv:
            from rc0.output import csv_tsv

            return csv_tsv.render(data, columns=columns, delimiter="\t")
        case OutputFormat.plain:
            from rc0.output import plain

            return plain.render(data, columns=columns)


__all__ = ["OutputFormat", "render", "resolve_default", "stdout_is_tty"]

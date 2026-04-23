"""CSV/TSV output.

CSV: quoted per RFC 4180. TSV: no quoting (newlines inside fields are stripped).
"""

from __future__ import annotations

import csv
import io
from typing import TYPE_CHECKING, Any

from rc0.output._format import stringify

if TYPE_CHECKING:
    from collections.abc import Sequence


def render(data: Any, *, columns: Sequence[str] | None = None, delimiter: str = ",") -> str:
    rows = _as_rows(data, columns=columns)
    if not rows:
        return ""
    field_names = list(rows[0].keys())
    buf = io.StringIO()
    if delimiter == "\t":
        writer = csv.writer(buf, delimiter="\t", quoting=csv.QUOTE_NONE, escapechar="\\")
        writer.writerow(field_names)
        for row in rows:
            writer.writerow([_sanitize_tsv(row.get(c)) for c in field_names])
    else:
        writer = csv.writer(buf, delimiter=delimiter, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(field_names)
        for row in rows:
            writer.writerow([stringify(row.get(c), list_sep=",") for c in field_names])
    return buf.getvalue().rstrip("\n")


def _as_rows(data: Any, *, columns: Sequence[str] | None) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        msg = "CSV/TSV output requires a list of dicts or a single dict."
        raise TypeError(msg)
    if not data:
        return []
    rows: list[dict[str, Any]] = []
    keys: list[str] = list(columns) if columns else list(data[0].keys())
    for item in data:
        if not isinstance(item, dict):
            msg = "CSV/TSV output requires every item to be a dict."
            raise TypeError(msg)
        rows.append({k: item.get(k) for k in keys})
    return rows


def _sanitize_tsv(value: Any) -> str:
    return stringify(value, list_sep=",").replace("\t", " ").replace("\n", " ")

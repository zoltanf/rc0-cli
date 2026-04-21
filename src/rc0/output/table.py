"""Rich-rendered table output."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from collections.abc import Sequence


def render(
    data: Any,
    *,
    columns: Sequence[str] | None = None,
    title: str | None = None,
) -> str:
    console = Console(record=True, soft_wrap=False)

    if data is None:
        return ""

    if isinstance(data, dict):
        table = _kv_table(data, title=title)
    elif isinstance(data, list):
        table = _list_table(data, columns=columns, title=title)
    else:
        return str(data)

    console.print(table)
    return console.export_text(styles=False).rstrip("\n")


def _kv_table(data: dict[str, Any], *, title: str | None) -> Table:
    table = Table(title=title, show_header=True, header_style="bold")
    table.add_column("key")
    table.add_column("value")
    for k, v in data.items():
        table.add_row(str(k), _stringify(v))
    return table


def _list_table(
    items: list[Any],
    *,
    columns: Sequence[str] | None,
    title: str | None,
) -> Table:
    table = Table(title=title, show_header=True, header_style="bold")
    dict_items: list[dict[str, Any]] = [x for x in items if isinstance(x, dict)]
    if dict_items:
        keys: list[str] = list(columns) if columns else list(dict_items[0].keys())
        for k in keys:
            table.add_column(k)
        for item in dict_items:
            table.add_row(*[_stringify(item.get(k)) for k in keys])
    else:
        table.add_column("value")
        for x in items:
            table.add_row(_stringify(x))
    return table


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list | tuple):
        return ", ".join(_stringify(v) for v in value)
    if isinstance(value, dict):
        return ", ".join(f"{k}={_stringify(v)}" for k, v in value.items())
    return str(value)

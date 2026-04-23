"""Output formatter tests."""

from __future__ import annotations

import json

import pytest
import yaml

from rc0.output import OutputFormat, render
from rc0.output import csv_tsv as csv_tsv_mod
from rc0.output import plain as plain_mod
from rc0.output import table as table_mod

DATA_LIST = [
    {"domain": "example.com", "type": "master", "dnssec": "yes"},
    {"domain": "example.net", "type": "slave", "dnssec": "no"},
]


def test_json_valid_and_indented() -> None:
    out = render(DATA_LIST, fmt=OutputFormat.json)
    parsed = json.loads(out)
    assert parsed == DATA_LIST
    assert "\n" in out  # indented


def test_json_compact() -> None:
    out = render(DATA_LIST, fmt=OutputFormat.json, compact=True)
    parsed = json.loads(out)
    assert parsed == DATA_LIST
    assert "\n" not in out


def test_yaml_roundtrip() -> None:
    out = render(DATA_LIST, fmt=OutputFormat.yaml)
    assert yaml.safe_load(out) == DATA_LIST


def test_csv_header_and_quoting() -> None:
    out = render(DATA_LIST, fmt=OutputFormat.csv)
    lines = out.splitlines()
    assert lines[0] == "domain,type,dnssec"
    assert lines[1] == "example.com,master,yes"


def test_tsv_uses_tabs_and_no_quotes() -> None:
    out = render(DATA_LIST, fmt=OutputFormat.tsv)
    lines = out.splitlines()
    assert lines[0].split("\t") == ["domain", "type", "dnssec"]
    assert lines[1] == "example.com\tmaster\tyes"


def test_plain_one_record_per_line() -> None:
    out = render(DATA_LIST, fmt=OutputFormat.plain)
    assert out == "example.com master yes\nexample.net slave no"


def test_table_contains_headers() -> None:
    # Use the table formatter directly so we bypass the stdout-TTY fallback
    # (render() falls back to plain when stdout is not a TTY, which is the
    # case inside pytest).
    out = table_mod.render(DATA_LIST)
    assert "domain" in out
    assert "example.com" in out


def test_unknown_format_raises() -> None:
    with pytest.raises(ValueError, match="Unknown output format"):
        render(DATA_LIST, fmt="not-a-format")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# table module — extended coverage
# ---------------------------------------------------------------------------


def test_table_none_returns_empty() -> None:
    assert table_mod.render(None) == ""


def test_table_dict_renders_kv() -> None:
    out = table_mod.render({"zone": "example.com", "active": True})
    assert "zone" in out
    assert "example.com" in out
    assert "active" in out
    assert "true" in out


def test_table_scalar_returns_str() -> None:
    assert table_mod.render(42) == "42"  # type: ignore[arg-type]


def test_table_list_with_non_dict_items() -> None:
    out = table_mod.render(["alpha", "beta"])
    assert "alpha" in out
    assert "beta" in out


def test_table_list_with_columns_filter() -> None:
    out = table_mod.render(DATA_LIST, columns=["domain"])
    assert "domain" in out
    assert "example.com" in out
    assert "type" not in out


def test_table_stringify_none() -> None:
    assert table_mod._stringify(None) == ""


def test_table_stringify_bool() -> None:
    assert table_mod._stringify(True) == "true"
    assert table_mod._stringify(False) == "false"


def test_table_stringify_list() -> None:
    assert table_mod._stringify([1, 2, 3]) == "1, 2, 3"


def test_table_stringify_tuple() -> None:
    assert table_mod._stringify(("a", "b")) == "a, b"


def test_table_stringify_dict() -> None:
    assert table_mod._stringify({"k": "v"}) == "k=v"


def test_table_with_title() -> None:
    out = table_mod.render(DATA_LIST, title="My Zones")
    assert "My Zones" in out


# ---------------------------------------------------------------------------
# plain module — extended coverage
# ---------------------------------------------------------------------------


def test_plain_none_returns_empty() -> None:
    assert plain_mod.render(None) == ""


def test_plain_scalar_returns_str() -> None:
    assert plain_mod.render(42) == "42"  # type: ignore[arg-type]


def test_plain_flat_list_of_scalars() -> None:
    out = plain_mod.render(["alpha", "beta", "gamma"])
    assert out == "alpha\nbeta\ngamma"


def test_plain_scalar_none() -> None:
    assert plain_mod._scalar(None) == "-"


def test_plain_scalar_bool() -> None:
    assert plain_mod._scalar(True) == "true"
    assert plain_mod._scalar(False) == "false"


def test_plain_with_columns() -> None:
    out = plain_mod.render(DATA_LIST, columns=["domain"])
    assert out == "example.com\nexample.net"


def test_plain_single_dict() -> None:
    out = plain_mod.render({"domain": "example.com", "type": "master"})
    assert out == "example.com master"


# ---------------------------------------------------------------------------
# csv_tsv module — extended coverage
# ---------------------------------------------------------------------------


def test_csv_tsv_single_dict() -> None:
    out = csv_tsv_mod.render({"a": 1, "b": 2})
    lines = out.splitlines()
    assert lines[0] == "a,b"
    assert lines[1] == "1,2"


def test_csv_tsv_empty_list() -> None:
    assert csv_tsv_mod.render([]) == ""


def test_csv_tsv_as_rows_non_list_raises() -> None:
    with pytest.raises(TypeError, match="list of dicts"):
        csv_tsv_mod._as_rows(42, columns=None)  # type: ignore[arg-type]


def test_csv_tsv_as_rows_non_dict_item_raises() -> None:
    with pytest.raises(TypeError, match="every item"):
        csv_tsv_mod._as_rows([{"a": 1}, "oops"], columns=None)


def test_csv_tsv_stringify_none() -> None:
    assert csv_tsv_mod._stringify(None) == ""


def test_csv_tsv_stringify_bool() -> None:
    assert csv_tsv_mod._stringify(True) == "true"
    assert csv_tsv_mod._stringify(False) == "false"


def test_csv_tsv_stringify_list() -> None:
    assert csv_tsv_mod._stringify([1, 2]) == "1,2"


def test_csv_tsv_stringify_tuple() -> None:
    assert csv_tsv_mod._stringify((1, 2)) == "1,2"


def test_tsv_sanitizes_tabs_and_newlines() -> None:
    data = [{"field": "has\ttab\nnewline"}]
    out = csv_tsv_mod.render(data, delimiter="\t")
    lines = out.splitlines()
    assert "\t" not in lines[1]
    assert "has tab newline" in lines[1]


def test_csv_with_columns_filter() -> None:
    out = csv_tsv_mod.render(DATA_LIST, columns=["domain"])
    lines = out.splitlines()
    assert lines[0] == "domain"
    assert lines[1] == "example.com"


def test_csv_none_and_bool_fields() -> None:
    data = [{"flag": True, "missing": None, "status": False}]
    out = csv_tsv_mod.render(data)
    lines = out.splitlines()
    assert lines[1] == "true,,false"

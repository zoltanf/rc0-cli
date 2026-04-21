"""Output formatter tests."""

from __future__ import annotations

import json

import pytest
import yaml

from rc0.output import OutputFormat, render
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

"""Argv-hoist pre-parser tests — ensures global flags work post-subcommand."""

from __future__ import annotations

from rc0.app import _hoist_global_flags


def test_no_hoist_needed() -> None:
    assert _hoist_global_flags(["-o", "json", "zone", "list"]) == [
        "-o",
        "json",
        "zone",
        "list",
    ]


def test_hoist_short_value_flag_after_subcommand() -> None:
    assert _hoist_global_flags(["zone", "list", "-o", "json", "--all"]) == [
        "-o",
        "json",
        "zone",
        "list",
        "--all",
    ]


def test_hoist_long_equals_form() -> None:
    assert _hoist_global_flags(["zone", "list", "--output=json"]) == [
        "--output=json",
        "zone",
        "list",
    ]


def test_hoist_multiple_bool_flags() -> None:
    assert _hoist_global_flags(
        ["dnssec", "sign", "example.com", "--dry-run", "-y"],
    ) == [
        "--dry-run",
        "-y",
        "dnssec",
        "sign",
        "example.com",
    ]


def test_double_dash_stops_hoisting() -> None:
    assert _hoist_global_flags(["record", "add", "--", "-o", "json"]) == [
        "record",
        "add",
        "--",
        "-o",
        "json",
    ]


def test_count_flag_preserved_across_repeats() -> None:
    assert _hoist_global_flags(["zone", "list", "-v", "-v"]) == [
        "-v",
        "-v",
        "zone",
        "list",
    ]


def test_value_flag_trailing_without_value() -> None:
    assert _hoist_global_flags(["zone", "list", "-o"]) == [
        "-o",
        "zone",
        "list",
    ]


def test_empty_argv() -> None:
    assert _hoist_global_flags([]) == []

"""Tests for rc0.rrsets.parse.from_flags."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from rc0.client.errors import ValidationError
from rc0.rrsets.parse import from_flags

if TYPE_CHECKING:
    from collections.abc import Callable


def _warn_sink() -> tuple[list[str], Callable[[str], None]]:
    captured: list[str] = []
    return captured, captured.append


def test_from_flags_single_content() -> None:
    _, sink = _warn_sink()
    change = from_flags(
        name="www",
        type_="A",
        ttl=3600,
        contents=["10.0.0.1"],
        disabled=False,
        changetype="add",
        zone="example.com",
        verbose=0,
        warn=sink,
    )
    assert change.name == "www.example.com."
    assert change.type == "A"
    assert change.ttl == 3600
    assert change.changetype == "add"
    assert [r.content for r in change.records] == ["10.0.0.1"]
    assert [r.disabled for r in change.records] == [False]


def test_from_flags_multiple_contents_aggregate() -> None:
    _, sink = _warn_sink()
    change = from_flags(
        name="www.example.com.",
        type_="A",
        ttl=3600,
        contents=["10.0.0.1", "10.0.0.2"],
        disabled=False,
        changetype="add",
        zone="example.com",
        verbose=0,
        warn=sink,
    )
    assert [r.content for r in change.records] == ["10.0.0.1", "10.0.0.2"]


def test_from_flags_delete_allows_empty_contents() -> None:
    _, sink = _warn_sink()
    change = from_flags(
        name="old",
        type_="A",
        ttl=3600,
        contents=[],
        disabled=False,
        changetype="delete",
        zone="example.com",
        verbose=0,
        warn=sink,
    )
    assert change.records == []


def test_from_flags_add_requires_contents() -> None:
    _, sink = _warn_sink()
    with pytest.raises(ValidationError):
        from_flags(
            name="www",
            type_="A",
            ttl=3600,
            contents=[],
            disabled=False,
            changetype="add",
            zone="example.com",
            verbose=0,
            warn=sink,
        )


def test_from_flags_trailing_dot_warn_emitted_in_verbose() -> None:
    captured, sink = _warn_sink()
    from_flags(
        name="www",
        type_="A",
        ttl=3600,
        contents=["10.0.0.1"],
        disabled=False,
        changetype="add",
        zone="example.com",
        verbose=1,
        warn=sink,
    )
    assert any("www.example.com." in line for line in captured)


def test_from_flags_no_warn_when_absolute() -> None:
    captured, sink = _warn_sink()
    from_flags(
        name="www.example.com.",
        type_="A",
        ttl=3600,
        contents=["10.0.0.1"],
        disabled=False,
        changetype="add",
        zone="example.com",
        verbose=1,
        warn=sink,
    )
    assert captured == []

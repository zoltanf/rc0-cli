"""Tests for interactive confirmation prompts."""

from __future__ import annotations

import io

import pytest

from rc0.client.errors import ConfirmationDeclined
from rc0.confirm import confirm_typed, confirm_yes_no


def test_confirm_typed_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("example.com\n"))
    err = io.StringIO()
    monkeypatch.setattr("sys.stderr", err)
    confirm_typed("example.com", summary="Would delete example.com.")
    assert "Would delete example.com." in err.getvalue()


def test_confirm_typed_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("other.test\n"))
    monkeypatch.setattr("sys.stderr", io.StringIO())
    with pytest.raises(ConfirmationDeclined):
        confirm_typed("example.com", summary="…")


def test_confirm_typed_empty_input_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    monkeypatch.setattr("sys.stderr", io.StringIO())
    with pytest.raises(ConfirmationDeclined):
        confirm_typed("example.com", summary="…")


def test_confirm_yes_no_accepts_y(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("y\n"))
    monkeypatch.setattr("sys.stderr", io.StringIO())
    confirm_yes_no("Proceed?")


def test_confirm_yes_no_accepts_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("yes\n"))
    monkeypatch.setattr("sys.stderr", io.StringIO())
    confirm_yes_no("Proceed?")


def test_confirm_yes_no_default_no(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("\n"))
    monkeypatch.setattr("sys.stderr", io.StringIO())
    with pytest.raises(ConfirmationDeclined):
        confirm_yes_no("Proceed?")


def test_confirm_yes_no_default_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("\n"))
    monkeypatch.setattr("sys.stderr", io.StringIO())
    confirm_yes_no("Proceed?", default_no=False)

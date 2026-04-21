"""The deprecated-command helper emits the stderr warning specified in §10."""

from __future__ import annotations

import pytest

from rc0.commands._deprecated import deprecated_warn


def test_deprecated_warn_writes_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    deprecated_warn("rc0 stats topmagnitude")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "[DEPRECATED]" in captured.err
    assert "rc0 stats topmagnitude" in captured.err


def test_deprecated_warn_can_be_suppressed_by_flag(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("RC0_SUPPRESS_DEPRECATED", "1")
    deprecated_warn("rc0 stats topmagnitude")
    captured = capsys.readouterr()
    assert captured.err == ""


def test_deprecated_warn_zero_does_not_suppress(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """=0 is a frequent 'disable' typo; confirm it does NOT suppress."""
    monkeypatch.setenv("RC0_SUPPRESS_DEPRECATED", "0")
    deprecated_warn("rc0 stats topmagnitude")
    captured = capsys.readouterr()
    assert "[DEPRECATED]" in captured.err


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "Yes", "on", "ON"])
def test_deprecated_warn_suppressed_by_truthy_values(
    value: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("RC0_SUPPRESS_DEPRECATED", value)
    deprecated_warn("rc0 stats topmagnitude")
    captured = capsys.readouterr()
    assert captured.err == ""

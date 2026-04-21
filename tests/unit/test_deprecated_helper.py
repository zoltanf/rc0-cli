"""The deprecated-command helper emits the stderr warning specified in §10."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rc0.commands._deprecated import deprecated_warn

if TYPE_CHECKING:
    import pytest


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

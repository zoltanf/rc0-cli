"""Unit tests for the usage-error hint helper in rc0.app."""

from __future__ import annotations

import click
from typer.main import get_command

from rc0.app import _format_usage_hint, app


def _ctx_for(name_path: list[str]) -> click.Context:
    """Build a click.Context for the leaf command at name_path, with parents
    chained so ``ctx.command_path`` renders the full chain (e.g. ``rc0 record set``)."""
    root = get_command(app)
    parent = click.Context(root, info_name="rc0")
    current: click.Command = root
    for name in name_path:
        assert isinstance(current, click.Group)
        sub = current.commands[name]
        parent = click.Context(sub, info_name=name, parent=parent)
        current = sub
    return parent


def test_hint_for_missing_option_on_record_set() -> None:
    ctx = _ctx_for(["record", "set"])
    exc = click.UsageError("Missing option '--name'.", ctx=ctx)
    hint = _format_usage_hint(exc)
    assert hint is not None
    assert "rc0 record set" in hint
    assert "--name NAME" in hint
    assert "--type TYPE" in hint


def test_hint_for_extra_positional_on_record_set() -> None:
    ctx = _ctx_for(["record", "set"])
    exc = click.UsageError("Got unexpected extra argument (www)", ctx=ctx)
    hint = _format_usage_hint(exc)
    assert hint is not None
    assert "this command takes flags" in hint
    assert "rc0 record set" in hint


def test_hint_uses_canonical_flag_not_python_name() -> None:
    # Typer maps `--type` to Python attr `type_` and `--content` to `contents`;
    # Click's default metavar would leak those Python names. The placeholder
    # must derive from the flag instead.
    ctx = _ctx_for(["record", "set"])
    exc = click.UsageError("Missing option '--name'.", ctx=ctx)
    hint = _format_usage_hint(exc)
    assert hint is not None
    assert "TYPE_" not in hint
    assert "CONTENTS" not in hint


def test_no_hint_when_ctx_is_none() -> None:
    exc = click.UsageError("Missing option '--name'.")
    assert _format_usage_hint(exc) is None


def test_no_hint_for_unrelated_message() -> None:
    ctx = _ctx_for(["record", "set"])
    exc = click.UsageError("No such option: --bogus", ctx=ctx)
    assert _format_usage_hint(exc) is None


def test_no_hint_when_no_required_options() -> None:
    ctx = _ctx_for(["version"])
    exc = click.UsageError("Missing argument 'X'.", ctx=ctx)
    assert _format_usage_hint(exc) is None


def test_hint_works_for_record_append() -> None:
    ctx = _ctx_for(["record", "append"])
    exc = click.UsageError("Got unexpected extra argument (www)", ctx=ctx)
    hint = _format_usage_hint(exc)
    assert hint is not None
    assert "rc0 record append" in hint
    assert "--name" in hint

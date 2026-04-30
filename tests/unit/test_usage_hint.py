"""Unit tests for the usage-error hint helper in rc0.app.

The helper turns Click's generic "Missing option" / "Got unexpected extra
argument" messages into an actionable next step that lists the command's
required flags. See feedback #6 in the v1.0.7 triage plan.
"""

from __future__ import annotations

import click
from typer.main import get_command

from rc0.app import _format_usage_hint, app
from rc0.commands import record as record_cmd


def _ctx_for(name_path: list[str]) -> click.Context:
    """Build a click.Context for the leaf command at name_path.

    Constructs nested parent contexts so ``ctx.command_path`` renders the
    full subcommand chain (e.g. ``rc0 record set``).
    """
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
    """`type_` / `contents` Python params should map to `--type` / `--content` placeholders."""
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
    """`rc0 version` takes no required options — nothing actionable to offer."""
    ctx = _ctx_for(["version"])
    exc = click.UsageError("Missing argument 'X'.", ctx=ctx)
    assert _format_usage_hint(exc) is None


def test_hint_works_for_record_append() -> None:
    """Coverage extends past `record set` — same handler covers the whole tree."""
    ctx = _ctx_for(["record", "append"])
    exc = click.UsageError("Got unexpected extra argument (www)", ctx=ctx)
    hint = _format_usage_hint(exc)
    assert hint is not None
    assert "rc0 record append" in hint
    assert "--name" in hint


def test_record_module_imported_for_resolution() -> None:
    """Sanity: importing `record` ensures Typer has registered the leaf commands."""
    assert "set" in get_command(record_cmd.app).commands
    assert "append" in get_command(record_cmd.app).commands

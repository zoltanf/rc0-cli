"""`rc0 introspect` — machine-readable schema of every command."""

from __future__ import annotations

import json
from typing import Any

import click
import typer

import rc0


def _walk(command: click.Command, path: list[str]) -> list[dict[str, Any]]:
    if isinstance(command, click.Group):
        out: list[dict[str, Any]] = []
        for name, sub in command.commands.items():
            out.extend(_walk(sub, [*path, name]))
        return out
    args: list[dict[str, Any]] = []
    flags: list[dict[str, Any]] = []
    for p in command.params:
        if isinstance(p, click.Argument):
            args.append({"name": p.name, "required": p.required})
        else:
            opt = p  # click.Option
            if not isinstance(opt, click.Option):
                continue
            name = opt.opts[0] if opt.opts else f"--{opt.name or ''}"
            flags.append(
                {
                    "name": name,
                    "help": opt.help or "",
                    "default": opt.default if not callable(opt.default) else None,
                }
            )
    help_text = (command.help or "").strip()
    summary = help_text.splitlines()[0] if help_text else ""
    return [
        {
            "path": path,
            "summary": summary,
            "description": help_text,
            "arguments": args,
            "flags": flags,
            "hidden": bool(command.hidden),
            "deprecated": bool(command.hidden) and "DEPRECATED" in help_text.upper(),
        },
    ]


def register(app: typer.Typer) -> None:
    """Attach ``introspect`` to the given Typer app."""

    @app.command("introspect")
    def introspect(ctx: typer.Context) -> None:
        """Emit a JSON schema of every rc0 command (for scripts and LLM agents)."""
        _ = ctx.obj  # touch AppState so Typer populates it
        click_app = typer.main.get_command(app)
        payload = {
            "rc0_version": rc0.__version__,
            "commands": _walk(click_app, []),
        }
        typer.echo(json.dumps(payload, indent=2))

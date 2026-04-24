"""`rc0 skill` — install or remove the rc0 Claude Code skill.

Writes a bundled ``SKILL.md`` into ``<scope>/.claude/skills/rc0/`` where
scope is either the current working directory (``--project``) or the
user's home directory (``--global``). The skill body is shipped as a
package resource (see :mod:`rc0.skill`) so it travels with the wheel and
the PyInstaller binary.
"""

from __future__ import annotations

import contextlib
from importlib import resources
from pathlib import Path

import typer

from rc0.app_state import AppState  # noqa: TC001
from rc0.confirm import confirm_yes_no

app = typer.Typer(
    name="skill",
    help="Manage the rc0 Claude Code skill.",
    no_args_is_help=True,
)

_SKILL_DIRNAME = "rc0"
_SKILL_FILENAME = "SKILL.md"


def _target_path(*, project: bool, global_: bool) -> Path:
    if project == global_:
        raise typer.BadParameter("pass exactly one of --project or --global")
    base = Path.cwd() if project else Path.home()
    return base / ".claude" / "skills" / _SKILL_DIRNAME / _SKILL_FILENAME


def _skill_body() -> str:
    return resources.files("rc0.skill").joinpath(_SKILL_FILENAME).read_text(encoding="utf-8")


@app.command("install")
def install_cmd(
    ctx: typer.Context,
    project: bool = typer.Option(
        False,
        "--project",
        help="Install to ./.claude/skills/rc0/SKILL.md.",
    ),
    global_: bool = typer.Option(
        False,
        "--global",
        "-g",
        help="Install to ~/.claude/skills/rc0/SKILL.md.",
    ),
) -> None:
    """Install the rc0 Claude Code skill.

    Exactly one of --project or --global is required. If the target file
    already exists, prompts for confirmation; pass -y to overwrite
    silently. Honors --dry-run.

    Examples:

      rc0 skill install --project
      rc0 skill install --global
      rc0 -y skill install -g
      rc0 --dry-run skill install --project
    """
    state: AppState = ctx.obj
    target = _target_path(project=project, global_=global_)
    body = _skill_body()

    if state.dry_run:
        typer.echo(f"would write {target}")
        return

    if target.exists() and not state.yes:
        confirm_yes_no(f"Would overwrite {target}.")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    typer.echo(f"wrote {target}")


@app.command("uninstall")
def uninstall_cmd(
    ctx: typer.Context,
    project: bool = typer.Option(
        False,
        "--project",
        help="Remove ./.claude/skills/rc0/SKILL.md.",
    ),
    global_: bool = typer.Option(
        False,
        "--global",
        "-g",
        help="Remove ~/.claude/skills/rc0/SKILL.md.",
    ),
) -> None:
    """Uninstall the rc0 Claude Code skill.

    Exactly one of --project or --global is required. Prompts for
    confirmation unless -y is passed. Idempotent: a missing file is not
    an error.

    Examples:

      rc0 skill uninstall --project
      rc0 -y skill uninstall -g
      rc0 --dry-run skill uninstall --global
    """
    state: AppState = ctx.obj
    target = _target_path(project=project, global_=global_)

    if not target.exists():
        typer.echo(f"not installed at {target}", err=True)
        return

    if state.dry_run:
        typer.echo(f"would remove {target}")
        return

    if not state.yes:
        confirm_yes_no(f"Would remove {target}.")

    target.unlink()
    # Best-effort cleanup of the now-empty rc0/ dir; leave .claude/skills/ alone.
    with contextlib.suppress(OSError):
        target.parent.rmdir()
    typer.echo(f"removed {target}")

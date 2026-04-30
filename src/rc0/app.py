"""Typer root app: global flags, shared state, subcommand wiring.

Follows mission plan §6 for global flag names and precedence rules.
"""

from __future__ import annotations

import logging
import os
import platform
import sys
from pathlib import Path
from typing import Annotated

import click
import typer

import rc0
from rc0.app_state import AppState
from rc0.client.errors import ConfirmationDeclined, Rc0Error
from rc0.commands import acme as acme_cmd
from rc0.commands import auth as auth_cmd
from rc0.commands import config as config_cmd
from rc0.commands import dnssec as dnssec_cmd
from rc0.commands import help as help_cmd
from rc0.commands import introspect as introspect_cmd
from rc0.commands import messages as messages_cmd
from rc0.commands import record as record_cmd
from rc0.commands import report as report_cmd
from rc0.commands import settings as settings_cmd
from rc0.commands import skill as skill_cmd
from rc0.commands import stats as stats_cmd
from rc0.commands import tsig as tsig_cmd
from rc0.commands import zone as zone_cmd
from rc0.config import load_profile
from rc0.output import OutputFormat, render

app = typer.Typer(
    name="rc0",
    help="The command line for RcodeZero DNS.",
    no_args_is_help=True,
    add_completion=True,
    rich_markup_mode="rich",
)

app.add_typer(acme_cmd.app, name="acme", help="Manage ACME DNS-01 challenge records.")
app.add_typer(auth_cmd.app, name="auth", help="Authenticate with the RcodeZero API.")
app.add_typer(config_cmd.app, name="config", help="Read and write rc0 configuration.")
app.add_typer(dnssec_cmd.app, name="dnssec", help="Manage DNSSEC for zones.")
app.add_typer(help_cmd.app, name="help", help="Long-form topic documentation.")
app.add_typer(messages_cmd.app, name="messages", help="Inspect queued account messages.")
app.add_typer(record_cmd.app, name="record", help="Manage RRsets.")
app.add_typer(report_cmd.app, name="report", help="Account-level reports.")
app.add_typer(settings_cmd.app, name="settings", help="Manage account-level settings.")
app.add_typer(skill_cmd.app, name="skill", help="Manage the rc0 Claude Code skill.")
app.add_typer(stats_cmd.app, name="stats", help="Account statistics.")
app.add_typer(tsig_cmd.app, name="tsig", help="Manage TSIG keys.")
app.add_typer(zone_cmd.app, name="zone", help="Manage RcodeZero zones.")

introspect_cmd.register(app)


OutputOption = Annotated[
    OutputFormat | None,
    typer.Option(
        "--output",
        "-o",
        help="Output format.",
        envvar="RC0_OUTPUT",
        case_sensitive=False,
    ),
]
ProfileOption = Annotated[
    str,
    typer.Option("--profile", help="Named config profile to use.", envvar="RC0_PROFILE"),
]
TokenOption = Annotated[
    str | None,
    typer.Option("--token", help="API bearer token.", envvar="RC0_API_TOKEN"),
]
ApiUrlOption = Annotated[
    str | None,
    typer.Option("--api-url", help="Base URL of the API.", envvar="RC0_API_URL"),
]
DryRunOption = Annotated[
    bool,
    typer.Option("--dry-run", help="Do not mutate; print intended request.", envvar="RC0_DRY_RUN"),
]
YesOption = Annotated[
    bool,
    typer.Option("--yes", "-y", help="Skip confirmation prompts.", envvar="RC0_YES"),
]
NoColorOption = Annotated[
    bool,
    typer.Option("--no-color", help="Disable ANSI colors.", envvar="NO_COLOR"),
]
QuietOption = Annotated[
    bool,
    typer.Option("--quiet", "-q", help="Suppress non-essential output."),
]
VerboseOption = Annotated[
    int,
    typer.Option(
        "--verbose",
        "-v",
        count=True,
        help="Increase log verbosity.",
        envvar="RC0_VERBOSE",
    ),
]
LogFileOption = Annotated[
    Path | None,
    typer.Option("--log-file", help="Write JSON-lines logs to this path.", envvar="RC0_LOG_FILE"),
]
TimeoutOption = Annotated[
    float | None,
    typer.Option("--timeout", help="HTTP timeout in seconds.", envvar="RC0_TIMEOUT"),
]
RetriesOption = Annotated[
    int | None,
    typer.Option("--retries", help="Retry count on idempotent 5xx/timeouts.", envvar="RC0_RETRIES"),
]
ConfigOption = Annotated[
    Path | None,
    typer.Option("--config", help="Explicit path to the config file.", envvar="RC0_CONFIG"),
]


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(
            f"rc0 {rc0.__version__} "
            f"(python {platform.python_version()}, {platform.system()} {platform.machine()})",
        )
        raise typer.Exit(code=0)


VersionOption = Annotated[
    bool,
    typer.Option(
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Print version and exit.",
    ),
]


@app.callback()
def root(
    ctx: typer.Context,
    profile: ProfileOption = "default",
    token: TokenOption = None,
    api_url: ApiUrlOption = None,
    output: OutputOption = None,
    timeout: TimeoutOption = None,
    retries: RetriesOption = None,
    dry_run: DryRunOption = False,
    yes: YesOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = 0,
    log_file: LogFileOption = None,
    config: ConfigOption = None,
    version: VersionOption = False,
) -> None:
    """Populate :class:`AppState` on the Typer context for subcommands."""
    _configure_logging(verbose=verbose, log_file=log_file)
    profile_cfg = load_profile(profile, path=_config_path_from_env())
    ctx.obj = AppState(
        profile_name=profile,
        profile=profile_cfg,
        token=token,
        api_url=api_url,
        output=output,
        timeout=timeout,
        retries=retries,
        dry_run=dry_run,
        yes=yes,
        no_color=no_color or _no_color_env(),
        quiet=quiet,
        verbose=verbose,
        log_file=log_file,
    )


@app.command("version")
def version_cmd(ctx: typer.Context) -> None:
    """Print version, Python, and platform."""
    state: AppState = ctx.obj
    payload = {
        "version": rc0.__version__,
        "python": platform.python_version(),
        "platform": f"{platform.system()} {platform.release()} {platform.machine()}",
    }
    typer.echo(render(payload, fmt=state.effective_output))


# ----------------------------------------------------------- internal helpers


def _derive_global_opt_sets() -> tuple[frozenset[str], frozenset[str]]:
    # Typer injects these when add_completion=True; they are eager and exit
    # immediately, so position-hoisting is unnecessary.
    typer_injected = {"--install-completion", "--show-completion"}
    value_opts: set[str] = set()
    noarg_opts: set[str] = set()
    for param in typer.main.get_command(app).params:
        if not isinstance(param, click.Option):
            continue
        target = noarg_opts if (param.is_flag or param.count) else value_opts
        for opt in (*param.opts, *param.secondary_opts):
            if opt in typer_injected:
                continue
            target.add(opt)
    return frozenset(value_opts), frozenset(noarg_opts)


_GLOBAL_VALUE_OPTS, _GLOBAL_NOARG_OPTS = _derive_global_opt_sets()


def _hoist_global_flags(argv: list[str]) -> list[str]:
    """Reorder argv so globally-declared flags parse regardless of position.

    Click's Group parser stops consuming group-level options at the first
    positional (the subcommand name), so ``rc0 zone list -o json`` fails
    with "No such option: -o". This pre-parser moves any token matching a
    known global option ahead of the subcommand. After a ``--`` sentinel,
    tokens are passed through untouched.
    """
    hoisted: list[str] = []
    remaining: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--":
            remaining.extend(argv[i:])
            break
        if arg.startswith("--") and "=" in arg:
            key = arg.split("=", 1)[0]
            if key in _GLOBAL_VALUE_OPTS or key in _GLOBAL_NOARG_OPTS:
                hoisted.append(arg)
                i += 1
                continue
        if arg in _GLOBAL_VALUE_OPTS:
            hoisted.append(arg)
            if i + 1 < len(argv):
                hoisted.append(argv[i + 1])
                i += 2
            else:
                i += 1
            continue
        if arg in _GLOBAL_NOARG_OPTS:
            hoisted.append(arg)
            i += 1
            continue
        remaining.append(arg)
        i += 1
    return hoisted + remaining


def _configure_logging(*, verbose: int, log_file: Path | None) -> None:
    level = logging.WARNING
    if verbose == 1:
        level = logging.INFO
    elif verbose >= 2:
        level = logging.DEBUG
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
    stderr_handler = logging.StreamHandler(stream=sys.stderr)
    stderr_handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
    root_logger.addHandler(stderr_handler)
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"),
        )
        root_logger.addHandler(file_handler)


def _config_path_from_env() -> Path | None:
    raw = os.environ.get("RC0_CONFIG")
    return Path(raw).expanduser() if raw else None


def _no_color_env() -> bool:
    return bool(os.environ.get("NO_COLOR"))


# ---------------------------------------------------------------- entrypoint


_USAGE_HINT_TRIGGERS = (
    "Missing option",
    "Missing argument",
    "Got unexpected extra argument",
)


def _format_usage_hint(exc: click.UsageError) -> str | None:
    """Return a hint listing the command's required flags, or None.

    Triggers when Click reports a missing option/argument or unexpected
    extra positional argument and the command has at least one required
    Option. Lists the canonical flag names so the correct invocation is
    one paste away.
    """
    ctx = exc.ctx
    if ctx is None:
        return None
    msg = exc.format_message() or ""
    if not any(trigger in msg for trigger in _USAGE_HINT_TRIGGERS):
        return None
    required = [
        param for param in ctx.command.params if isinstance(param, click.Option) and param.required
    ]
    if not required:
        return None
    flags = " ".join(f"{opt.opts[0]} {_placeholder(opt)}" for opt in required)
    return f"hint:  this command takes flags. Try: {ctx.command_path} {flags}"


def _placeholder(opt: click.Option) -> str:
    """Derive a metavar-style placeholder from the canonical flag name."""
    if opt.metavar:
        return opt.metavar
    return opt.opts[0].lstrip("-").replace("-", "_").upper()


def _run(argv: list[str]) -> int:
    """Inner entry point — separated so tests can drive it without subprocess."""
    try:
        app(args=_hoist_global_flags(argv), prog_name="rc0", standalone_mode=False)
    except click.exceptions.Exit as exc:
        return exc.exit_code
    except click.UsageError as exc:
        exc.show()
        hint = _format_usage_hint(exc)
        if hint:
            typer.echo(hint, err=True)
        return 2
    except ConfirmationDeclined as exc:
        typer.echo(f"error: {exc}", err=True)
        return exc.exit_code
    except Rc0Error as exc:
        typer.echo(f"error: {exc.message}", err=True)
        if exc.hint:
            typer.echo(f"hint:  {exc.hint}", err=True)
        return exc.exit_code
    except click.ClickException as exc:
        exc.show()
        return exc.exit_code
    except KeyboardInterrupt:
        return 130
    return 0


def main() -> None:
    """CLI entry point registered in ``pyproject.toml`` as ``rc0``."""
    sys.exit(_run(sys.argv[1:]))

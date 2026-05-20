"""Typer root app: global flags, shared state, subcommand wiring.

Follows mission plan §6 for global flag names and precedence rules.
"""

from __future__ import annotations

import importlib
import logging
import os
import platform
import sys
from pathlib import Path
from typing import Annotated

import click
import typer
from typer.core import TyperGroup

import rc0
from rc0.app_state import AppState
from rc0.client.errors import ConfirmationDeclined, Rc0Error
from rc0.commands import introspect as introspect_cmd
from rc0.config import load_profile
from rc0.output import OutputFormat, render

# Subcommands are resolved on demand to keep cold startup under 200ms in the
# packaged binary. Each entry maps the user-visible name to the module that
# defines the Typer subapp plus the short help shown on ``rc0 --help``. The
# help text mirrors the value previously passed to ``add_typer(help=...)`` so
# ``rc0 --help`` can be rendered without importing any of these modules.
_LAZY_SUBCOMMANDS: dict[str, tuple[str, str]] = {
    "acme": ("rc0.commands.acme", "Manage ACME DNS-01 challenge records."),
    "auth": ("rc0.commands.auth", "Authenticate with the RcodeZero API."),
    "config": ("rc0.commands.config", "Read and write rc0 configuration."),
    "dnssec": ("rc0.commands.dnssec", "Manage DNSSEC for zones."),
    "help": ("rc0.commands.help", "Long-form topic documentation."),
    "messages": ("rc0.commands.messages", "Inspect queued account messages."),
    "record": ("rc0.commands.record", "Manage RRsets."),
    "report": ("rc0.commands.report", "Account-level reports."),
    "settings": ("rc0.commands.settings", "Manage account-level settings."),
    "skill": ("rc0.commands.skill", "Manage the rc0 Claude Code skill."),
    "stats": ("rc0.commands.stats", "Account statistics."),
    "tsig": ("rc0.commands.tsig", "Manage TSIG keys."),
    "zone": ("rc0.commands.zone", "Manage RcodeZero zones."),
}


class _LazyStub(click.Group):
    """Placeholder group that defers importing its module until needed.

    Rendering ``rc0 --help`` only reads ``name``/``short_help``/``hidden``/
    ``help`` on each command, which this stub provides eagerly. Anything that
    actually inspects or invokes the subcommand (descending into it during
    parsing, listing its nested commands for ``introspect``, asking for its
    own help) forwards to the real Typer subapp, importing it lazily.
    """

    def __init__(self, name: str, module_path: str, help_text: str) -> None:
        super().__init__(name=name, help=help_text, short_help=help_text)
        self._module_path = module_path
        self._real: click.Group | None = None

    def _resolve(self) -> click.Group:
        if self._real is None:
            module = importlib.import_module(self._module_path)
            real = typer.main.get_command(module.app)
            assert isinstance(real, click.Group), f"{self._module_path}.app must be a Typer group"
            if self.help and not real.help:
                real.help = self.help
            self._real = real
        return self._real

    def list_commands(self, ctx: click.Context) -> list[str]:
        return self._resolve().list_commands(ctx)

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        return self._resolve().get_command(ctx, cmd_name)

    def get_params(self, ctx: click.Context) -> list[click.Parameter]:
        return self._resolve().get_params(ctx)

    def make_context(
        self,
        info_name: str | None,
        args: list[str],
        parent: click.Context | None = None,
        **extra: object,
    ) -> click.Context:
        real = self._resolve()
        assert self.name is not None
        if parent is not None and isinstance(parent.command, click.Group):
            parent.command.commands[self.name] = real
        return real.make_context(info_name, args, parent=parent, **extra)

    def invoke(self, ctx: click.Context) -> object:
        return self._resolve().invoke(ctx)

    def get_help(self, ctx: click.Context) -> str:
        return self._resolve().get_help(ctx)

    def get_usage(self, ctx: click.Context) -> str:
        return self._resolve().get_usage(ctx)


class LazyTyperGroup(TyperGroup):
    """Top-level group that imports each subcommand module on first access.

    ``rc0 --help`` and ``rc0 --version`` should never pay for httpx, pydantic,
    or rich-formatter import time. The stubs in ``self.commands`` expose
    enough metadata for Typer's rich help to render without triggering any
    subcommand import; ``rc0.commands.X`` is imported only when the user
    actually invokes the matching subcommand.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        for name, (module_path, help_text) in _LAZY_SUBCOMMANDS.items():
            self.commands.setdefault(name, _LazyStub(name, module_path, help_text))


app = typer.Typer(
    name="rc0",
    help="The command line for RcodeZero DNS.",
    no_args_is_help=True,
    add_completion=True,
    rich_markup_mode="rich",
    cls=LazyTyperGroup,
)

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

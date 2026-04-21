"""`rc0 config` — show / get / set / unset / path."""

from __future__ import annotations

from typing import Annotated, Any

import typer

from rc0 import config as config_core
from rc0.app_state import AppState  # noqa: TC001
from rc0.client.errors import ConfigError
from rc0.output import render

app = typer.Typer(
    name="config",
    help="Read and write rc0 configuration.",
    no_args_is_help=True,
)


@app.command("show")
def show(ctx: typer.Context) -> None:
    """Print the effective config for the active profile."""
    state: AppState = ctx.obj
    payload = {
        "profile": state.profile_name,
        "api_url": state.effective_api_url,
        "output": state.effective_output.value,
        "timeout": state.effective_timeout,
        "retries": state.effective_retries,
        "config_path": str(config_core.config_path()),
    }
    typer.echo(render(payload, fmt=state.effective_output))


@app.command("get")
def get_value(
    ctx: typer.Context,
    key: Annotated[
        str,
        typer.Argument(help="Config key, e.g. api_url / output / timeout / retries."),
    ],
) -> None:
    """Print the value of one config key in the active profile."""
    state: AppState = ctx.obj
    values: dict[str, Any] = {
        "api_url": state.effective_api_url,
        "output": state.effective_output.value,
        "timeout": state.effective_timeout,
        "retries": state.effective_retries,
    }
    if key not in values:
        raise ConfigError(
            f"Unknown config key {key!r}.",
            hint="Valid keys: api_url, output, timeout, retries.",
        )
    typer.echo(render({key: values[key]}, fmt=state.effective_output))


@app.command("set")
def set_value(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument()],
    value: Annotated[str, typer.Argument()],
) -> None:
    """Set one config key (persists to the config file)."""
    state: AppState = ctx.obj
    path = config_core.set_value(key, value, profile=state.profile_name)
    typer.echo(
        render(
            {"profile": state.profile_name, "key": key, "value": value, "path": str(path)},
            fmt=state.effective_output,
        )
    )


@app.command("unset")
def unset_value(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument()],
) -> None:
    """Remove one config key from the active profile."""
    state: AppState = ctx.obj
    path = config_core.unset_value(key, profile=state.profile_name)
    typer.echo(
        render(
            {"profile": state.profile_name, "removed": key, "path": str(path)},
            fmt=state.effective_output,
        )
    )


@app.command("path")
def path_cmd(ctx: typer.Context) -> None:
    """Print the effective config file path."""
    state: AppState = ctx.obj
    typer.echo(render({"path": str(config_core.config_path())}, fmt=state.effective_output))

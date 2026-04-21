"""AppState — global CLI flags distilled into a dataclass.

Lives in its own module to avoid circular imports: command modules import
``AppState`` here, while :mod:`rc0.app` populates it in the Typer callback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from rc0.config import ProfileConfig

if TYPE_CHECKING:
    from pathlib import Path

    from rc0.output import OutputFormat


@dataclass
class AppState:
    profile_name: str = "default"
    profile: ProfileConfig = field(default_factory=ProfileConfig)
    token: str | None = None
    api_url: str | None = None
    output: OutputFormat | None = None
    timeout: float | None = None
    retries: int | None = None
    dry_run: bool = False
    yes: bool = False
    no_color: bool = False
    quiet: bool = False
    verbose: int = 0
    log_file: Path | None = None

    @property
    def effective_api_url(self) -> str:
        return self.api_url or self.profile.api_url

    @property
    def effective_output(self) -> OutputFormat:
        from rc0.output import OutputFormat

        if self.output is not None:
            return self.output
        return OutputFormat(self.profile.output)

    @property
    def effective_timeout(self) -> float:
        return self.timeout if self.timeout is not None else self.profile.timeout

    @property
    def effective_retries(self) -> int:
        return self.retries if self.retries is not None else self.profile.retries

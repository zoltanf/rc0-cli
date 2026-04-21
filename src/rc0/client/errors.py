"""Exception hierarchy with HTTP-status and exit-code mapping.

See mission plan §11 for the full table. Each exception carries an ``exit_code``
(used by the CLI entry point) and a stable string ``code`` (surfaced in
machine-readable error output).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import IO, Any, ClassVar

from click.exceptions import ClickException


@dataclass
class RequestSummary:
    """Minimal summary of the HTTP request that triggered an error."""

    method: str
    url: str
    request_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"method": self.method, "url": self.url}
        if self.request_id is not None:
            d["id"] = self.request_id
        return d


class Rc0Error(ClickException):
    """Base class for all rc0-raised errors.

    Inherits from :class:`click.ClickException` so that both our hand-rolled
    :func:`rc0.app.main` wrapper and Click's standard standalone-mode exit
    handler (used by Typer's CliRunner in tests) honour :attr:`exit_code`.
    """

    exit_code = 1
    code: ClassVar[str] = "RC0_ERROR"

    def __init__(
        self,
        message: str,
        *,
        hint: str | None = None,
        http_status: int | None = None,
        request: RequestSummary | None = None,
        docs: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.http_status = http_status
        self.request = request
        self.docs = docs

    def format_message(self) -> str:
        return self.message

    def show(self, file: IO[Any] | None = None) -> None:
        """Called by Click when the exception propagates out of a command."""
        stream = file or sys.stderr
        stream.write(f"error: {self.message}\n")
        if self.hint:
            stream.write(f"hint:  {self.hint}\n")

    def to_dict(self) -> dict[str, Any]:
        """Render as the §11 error JSON shape."""
        body: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.http_status is not None:
            body["http_status"] = self.http_status
        if self.request is not None:
            body["request"] = self.request.to_dict()
        if self.hint is not None:
            body["hint"] = self.hint
        if self.docs is not None:
            body["docs"] = self.docs
        return {"error": body}


class ConfigError(Rc0Error):
    exit_code = 3
    code: ClassVar[str] = "CONFIG_ERROR"


class AuthError(Rc0Error):
    """HTTP 401 — missing or invalid token."""

    exit_code = 4
    code: ClassVar[str] = "AUTH_ERROR"


class AuthzError(Rc0Error):
    """HTTP 403 — token lacks required permission."""

    exit_code = 5
    code: ClassVar[str] = "AUTHZ_ERROR"


class NotFoundError(Rc0Error):
    """HTTP 404."""

    exit_code = 6
    code: ClassVar[str] = "NOT_FOUND"


class ValidationError(Rc0Error):
    """HTTP 400 with structured body, or client-side validation failure."""

    exit_code = 7
    code: ClassVar[str] = "VALIDATION_ERROR"

    def __init__(
        self,
        message: str,
        *,
        field_errors: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.field_errors = field_errors or []

    def to_dict(self) -> dict[str, Any]:
        out = super().to_dict()
        if self.field_errors:
            out["error"]["fields"] = self.field_errors
        return out


class ConflictError(Rc0Error):
    """HTTP 409 — resource already exists or state conflict."""

    exit_code = 8
    code: ClassVar[str] = "CONFLICT"


class RateLimitError(Rc0Error):
    """HTTP 429."""

    exit_code = 9
    code: ClassVar[str] = "RATE_LIMITED"

    def __init__(self, message: str, *, retry_after: float | None = None, **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class NetworkError(Rc0Error):
    """Connection failure, DNS failure, or timeout."""

    exit_code = 10
    code: ClassVar[str] = "NETWORK_ERROR"


class ServerError(Rc0Error):
    """HTTP 5xx after all retries are exhausted."""

    exit_code = 11
    code: ClassVar[str] = "SERVER_ERROR"


class ConfirmationDeclined(Rc0Error):
    """User answered 'no' (or provided the wrong confirmation token) to a destructive prompt."""

    exit_code = 12
    code: ClassVar[str] = "CONFIRMATION_DECLINED"


HTTP_STATUS_TO_EXCEPTION: dict[int, type[Rc0Error]] = {
    400: ValidationError,
    401: AuthError,
    403: AuthzError,
    404: NotFoundError,
    409: ConflictError,
    429: RateLimitError,
}


def from_http_status(
    status: int,
    message: str,
    *,
    hint: str | None = None,
    request: RequestSummary | None = None,
    **extra: Any,
) -> Rc0Error:
    """Construct the appropriate Rc0Error subclass for an HTTP status."""
    if status >= 500:
        cls: type[Rc0Error] = ServerError
    else:
        cls = HTTP_STATUS_TO_EXCEPTION.get(status, Rc0Error)
    if cls is RateLimitError:
        retry_after = extra.pop("retry_after", None)
        err: Rc0Error = RateLimitError(
            message,
            hint=hint,
            http_status=status,
            request=request,
            retry_after=retry_after,
        )
        return err
    if cls is ValidationError:
        field_errors = extra.pop("field_errors", None)
        return ValidationError(
            message,
            hint=hint,
            http_status=status,
            request=request,
            field_errors=field_errors,
        )
    return cls(message, hint=hint, http_status=status, request=request)


ALL_EXIT_CODES: dict[int, str] = {
    0: "success",
    1: "generic error",
    2: "usage error (bad flags, missing arguments)",
    3: "config error",
    4: "authentication error (401)",
    5: "authorization / permission error (403)",
    6: "not found (404)",
    7: "validation error (400)",
    8: "conflict / already exists (409)",
    9: "rate limited (429)",
    10: "network / timeout / DNS failure",
    11: "server error (5xx after retries)",
    12: "confirmation declined by user",
    130: "interrupted (SIGINT)",
}

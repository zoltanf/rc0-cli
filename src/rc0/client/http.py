"""Thin httpx.Client wrapper: bearer auth, retries, logging with redaction.

Only the v0.1.0 surface is implemented here. Paginated helpers and mutation
builders land in Phase 1 and Phase 2 respectively.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import httpx

from rc0.client.errors import (
    NetworkError,
    RateLimitError,
    Rc0Error,
    RequestSummary,
    ServerError,
    from_http_status,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

REDACTED = "***REDACTED***"
RETRYABLE_STATUSES: frozenset[int] = frozenset({429, 502, 503, 504})

log = logging.getLogger("rc0.http")


@dataclass
class RetryPolicy:
    """Exponential backoff with jitter. Only GETs are retried."""

    max_retries: int = 3
    base_delay: float = 0.5
    factor: float = 2.0
    max_delay: float = 8.0

    def delay_for(self, attempt: int) -> float:
        exp = min(self.max_delay, self.base_delay * (self.factor**attempt))
        return exp * (0.5 + random.random() * 0.5)  # noqa: S311  # jitter, not crypto


@dataclass
class Client:
    """HTTP client for the RcodeZero API.

    The token is stored separately from the httpx.Client's default_headers so
    redaction is guaranteed when we log requests.
    """

    api_url: str
    token: str | None = None
    timeout: float = 30.0
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    verify: bool | str = True
    _client: httpx.Client = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._client = httpx.Client(
            base_url=self.api_url,
            timeout=self.timeout,
            verify=self.verify,
            http2=False,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Client:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ headers

    def _auth_headers(self) -> dict[str, str]:
        if self.token is None:
            return {}
        return {"Authorization": f"Bearer {self.token}"}

    @staticmethod
    def redact_headers(headers: Mapping[str, str]) -> dict[str, str]:
        """Return a copy of ``headers`` with ``Authorization`` redacted.

        Always pass headers through this before logging or emitting them in
        dry-run output.
        """
        out: dict[str, str] = {}
        for k, v in headers.items():
            if k.lower() == "authorization":
                out[k] = f"Bearer {REDACTED}"
            else:
                out[k] = v
        return out

    # --------------------------------------------------------------------- core

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any = None,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        """Perform a request with retries on idempotent GETs only."""
        merged_headers = {**self._auth_headers(), **(dict(headers) if headers else {})}
        attempts = self.retry_policy.max_retries + 1 if method.upper() == "GET" else 1
        last_exc: Exception | None = None

        for attempt in range(attempts):
            try:
                log.debug(
                    "%s %s headers=%s params=%s",
                    method,
                    path,
                    self.redact_headers(merged_headers),
                    params,
                )
                response = self._client.request(
                    method,
                    path,
                    params=params,
                    json=json,
                    headers=merged_headers,
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                if attempt >= attempts - 1:
                    raise NetworkError(
                        f"{type(exc).__name__} contacting {self.api_url}{path}: {exc}",
                        hint="Check network connectivity and --timeout / --retries.",
                    ) from exc
                time.sleep(self.retry_policy.delay_for(attempt))
                continue

            if response.status_code < 400:
                return response

            if response.status_code in RETRYABLE_STATUSES and attempt < attempts - 1:
                retry_after = _retry_after_seconds(response)
                sleep_for = (
                    retry_after if retry_after is not None else self.retry_policy.delay_for(attempt)
                )
                time.sleep(sleep_for)
                continue

            raise self._exception_for_response(method, path, response)

        # Should only reach here if retries exhausted on NetworkError path.
        if last_exc is not None:
            raise NetworkError(
                f"Exhausted retries contacting {self.api_url}{path}: {last_exc}",
            ) from last_exc
        raise ServerError(
            f"Exhausted retries contacting {self.api_url}{path}",
        )

    # ----------------------------------------------------------- helpers/raise

    def _exception_for_response(
        self,
        method: str,
        path: str,
        response: httpx.Response,
    ) -> Rc0Error:
        request_summary = RequestSummary(
            method=method.upper(),
            url=str(response.request.url),
            request_id=response.headers.get("x-request-id"),
        )
        message, hint, field_errors = _extract_error_body(response)
        status = response.status_code
        kwargs: dict[str, Any] = {"hint": hint, "request": request_summary}
        if status == 400 and field_errors is not None:
            kwargs["field_errors"] = field_errors
        if status == 429:
            kwargs["retry_after"] = _retry_after_seconds(response)
            err = RateLimitError(
                message or f"Rate limited by {self.api_url}",
                http_status=status,
                **kwargs,
            )
            return err
        return from_http_status(
            status,
            message or f"HTTP {status} from {self.api_url}{path}",
            **kwargs,
        )

    # ---------------------------------------------------------------- wrappers

    def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("DELETE", path, **kwargs)


def _retry_after_seconds(response: httpx.Response) -> float | None:
    raw = response.headers.get("retry-after")
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _extract_error_body(
    response: httpx.Response,
) -> tuple[str | None, str | None, list[dict[str, Any]] | None]:
    """Try to pull a useful message/hint/fields out of a JSON error body."""
    content_type = response.headers.get("content-type", "")
    if "json" not in content_type.lower():
        return response.text.strip() or None, None, None
    try:
        body = response.json()
    except ValueError:
        return response.text.strip() or None, None, None
    if not isinstance(body, dict):
        return str(body), None, None
    message = body.get("message") or body.get("detail") or body.get("error")
    hint = body.get("hint")
    fields = body.get("errors") or body.get("fields")
    if isinstance(fields, list):
        field_errors: list[dict[str, Any]] = [f for f in fields if isinstance(f, dict)]
    else:
        field_errors = []
    return (
        str(message) if message is not None else None,
        str(hint) if hint is not None else None,
        field_errors or None,
    )

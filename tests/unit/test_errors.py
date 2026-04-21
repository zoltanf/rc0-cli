"""Tests for the exception hierarchy and HTTP-status mapping (§11)."""

from __future__ import annotations

import pytest

from rc0.client.errors import (
    AuthError,
    AuthzError,
    ConflictError,
    NotFoundError,
    RateLimitError,
    RequestSummary,
    ServerError,
    ValidationError,
    from_http_status,
)


def test_exit_code_per_status() -> None:
    cases = [
        (400, ValidationError, 7),
        (401, AuthError, 4),
        (403, AuthzError, 5),
        (404, NotFoundError, 6),
        (409, ConflictError, 8),
        (429, RateLimitError, 9),
        (500, ServerError, 11),
        (502, ServerError, 11),
        (503, ServerError, 11),
    ]
    for status, cls, exit_code in cases:
        exc = from_http_status(status, "boom")
        assert isinstance(exc, cls)
        assert exc.exit_code == exit_code
        assert exc.http_status == status


def test_to_dict_has_stable_shape() -> None:
    exc = from_http_status(
        409,
        "Zone exists",
        hint="Use show",
        request=RequestSummary(method="POST", url="http://x/api/v2/zones", request_id="abc"),
    )
    body = exc.to_dict()
    assert body == {
        "error": {
            "code": "CONFLICT",
            "message": "Zone exists",
            "http_status": 409,
            "hint": "Use show",
            "request": {"method": "POST", "url": "http://x/api/v2/zones", "id": "abc"},
        }
    }


def test_validation_error_carries_field_errors() -> None:
    exc = from_http_status(400, "bad", field_errors=[{"field": "domain", "msg": "required"}])
    assert isinstance(exc, ValidationError)
    assert exc.field_errors == [{"field": "domain", "msg": "required"}]
    body = exc.to_dict()
    assert body["error"]["fields"] == [{"field": "domain", "msg": "required"}]


def test_rate_limit_records_retry_after() -> None:
    exc = from_http_status(429, "slow down", retry_after=5.0)
    assert isinstance(exc, RateLimitError)
    assert exc.retry_after == pytest.approx(5.0)

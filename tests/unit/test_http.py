"""HTTP client tests: redaction and error mapping."""

from __future__ import annotations

import httpx
import pytest
import respx

from rc0.client.errors import AuthError, AuthzError, ConflictError, NetworkError, NotFoundError
from rc0.client.http import REDACTED, Client


def test_redact_headers_hides_authorization() -> None:
    redacted = Client.redact_headers({"Authorization": "Bearer s3cret", "X-Other": "keep"})
    assert redacted["Authorization"] == f"Bearer {REDACTED}"
    assert redacted["X-Other"] == "keep"


def test_redact_headers_case_insensitive() -> None:
    redacted = Client.redact_headers({"authorization": "Bearer s3cret"})
    assert redacted["authorization"] == f"Bearer {REDACTED}"


@respx.mock
def test_get_returns_response_on_200() -> None:
    respx.get("https://api.test/api/v2/zones").mock(
        return_value=httpx.Response(200, json={"items": []}),
    )
    with Client(api_url="https://api.test", token="tk") as c:
        r = c.get("/api/v2/zones")
    assert r.status_code == 200


@pytest.mark.parametrize(
    ("status", "exc_cls"),
    [
        (401, AuthError),
        (403, AuthzError),
        (404, NotFoundError),
        (409, ConflictError),
    ],
)
@respx.mock
def test_error_mapping(status: int, exc_cls: type[Exception]) -> None:
    respx.get("https://api.test/api/v2/zones").mock(
        return_value=httpx.Response(status, json={"message": "nope"}),
    )
    with Client(api_url="https://api.test", token="tk") as c, pytest.raises(exc_cls):
        c.get("/api/v2/zones")


@respx.mock
def test_network_error_is_wrapped() -> None:
    respx.get("https://api.test/api/v2/zones").mock(side_effect=httpx.ConnectError("boom"))
    with Client(api_url="https://api.test", token="tk") as c, pytest.raises(NetworkError):
        c.get("/api/v2/zones")


@respx.mock
def test_get_retries_on_503_and_recovers() -> None:
    route = respx.get("https://api.test/api/v2/zones")
    route.side_effect = [
        httpx.Response(503),
        httpx.Response(200, json={"items": []}),
    ]
    # Zero-delay retries for the test.
    with Client(api_url="https://api.test", token="tk") as c:
        c.retry_policy.base_delay = 0.0
        r = c.get("/api/v2/zones")
    assert r.status_code == 200
    assert route.call_count == 2


@respx.mock
def test_post_does_not_retry() -> None:
    route = respx.post("https://api.test/api/v2/zones")
    route.side_effect = [httpx.Response(503), httpx.Response(200)]
    from rc0.client.errors import ServerError

    with Client(api_url="https://api.test", token="tk") as c:
        c.retry_policy.base_delay = 0.0
        with pytest.raises(ServerError):
            c.post("/api/v2/zones", json={"domain": "example.com"})
    assert route.call_count == 1

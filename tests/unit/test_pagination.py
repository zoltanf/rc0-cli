"""Paginator iterates the API's page/page_size protocol and aggregates for --all."""

from __future__ import annotations

import httpx
import pytest
import respx

from rc0.client.errors import ServerError
from rc0.client.http import Client
from rc0.client.pagination import iter_all, iter_pages


@respx.mock
def test_iter_pages_walks_until_short_page() -> None:
    respx.get("https://api.test/api/v2/zones", params={"page": 1, "page_size": 2}).mock(
        return_value=httpx.Response(200, json=[{"domain": "a"}, {"domain": "b"}]),
    )
    respx.get("https://api.test/api/v2/zones", params={"page": 2, "page_size": 2}).mock(
        return_value=httpx.Response(200, json=[{"domain": "c"}]),
    )
    with Client(api_url="https://api.test", token="tk") as c:
        pages = list(iter_pages(c, "/api/v2/zones", page_size=2))
    assert pages == [
        [{"domain": "a"}, {"domain": "b"}],
        [{"domain": "c"}],
    ]


@respx.mock
def test_iter_all_flattens_pages() -> None:
    respx.get("https://api.test/api/v2/zones").mock(
        side_effect=[
            httpx.Response(200, json=[{"domain": "a"}, {"domain": "b"}]),
            httpx.Response(200, json=[{"domain": "c"}]),
        ],
    )
    with Client(api_url="https://api.test", token="tk") as c:
        rows = list(iter_all(c, "/api/v2/zones", page_size=2))
    assert [r["domain"] for r in rows] == ["a", "b", "c"]


@respx.mock
def test_iter_pages_single_page() -> None:
    respx.get("https://api.test/api/v2/zones", params={"page": 1, "page_size": 50}).mock(
        return_value=httpx.Response(200, json=[{"domain": "only"}]),
    )
    with Client(api_url="https://api.test", token="tk") as c:
        pages = list(iter_pages(c, "/api/v2/zones", page_size=50))
    assert pages == [[{"domain": "only"}]]


@respx.mock
def test_iter_pages_raises_server_error_on_non_list_payload() -> None:
    respx.get("https://api.test/api/v2/zones").mock(
        return_value=httpx.Response(200, json={"error": "unexpected"}),
    )
    with (
        Client(api_url="https://api.test", token="tk") as c,
        pytest.raises(ServerError) as exc_info,
    ):
        list(iter_pages(c, "/api/v2/zones", page_size=2))
    assert exc_info.value.code == "SERVER_ERROR"
    assert exc_info.value.request is not None
    assert exc_info.value.request.method == "GET"


def test_iter_pages_rejects_zero_page_size() -> None:
    with (
        Client(api_url="https://api.test", token="tk") as c,
        pytest.raises(ValueError, match="page_size"),
    ):
        list(iter_pages(c, "/api/v2/zones", page_size=0))


@respx.mock
def test_iter_pages_params_cannot_override_pagination() -> None:
    route = respx.get(
        "https://api.test/api/v2/zones",
        params={"page": 1, "page_size": 2, "name": "x"},
    )
    route.mock(return_value=httpx.Response(200, json=[]))
    with Client(api_url="https://api.test", token="tk") as c:
        # Caller tries to sneak page=99 via params; the iterator must ignore that.
        list(iter_pages(c, "/api/v2/zones", page_size=2, params={"name": "x", "page": 99}))
    assert route.called

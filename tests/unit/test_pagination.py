"""Paginator iterates the API's page/page_size protocol and aggregates for --all."""

from __future__ import annotations

import httpx
import respx

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

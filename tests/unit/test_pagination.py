"""Paginator handles Laravel envelopes and bare arrays, plus error paths."""

from __future__ import annotations

import httpx
import pytest
import respx

from rc0.client.errors import ServerError
from rc0.client.http import Client
from rc0.client.pagination import PageInfo, fetch_page, iter_all, iter_pages

# ------------------------------------------------------------------ bare array


@respx.mock
def test_bare_array_walks_until_short_page() -> None:
    respx.get("https://api.test/api/v2/tsig", params={"page": 1, "page_size": 2}).mock(
        return_value=httpx.Response(200, json=[{"name": "a"}, {"name": "b"}]),
    )
    respx.get("https://api.test/api/v2/tsig", params={"page": 2, "page_size": 2}).mock(
        return_value=httpx.Response(200, json=[{"name": "c"}]),
    )
    with Client(api_url="https://api.test", token="tk") as c:
        pages = list(iter_pages(c, "/api/v2/tsig", page_size=2))
    assert pages == [[{"name": "a"}, {"name": "b"}], [{"name": "c"}]]


@respx.mock
def test_bare_array_single_page() -> None:
    respx.get("https://api.test/api/v2/tsig", params={"page": 1, "page_size": 50}).mock(
        return_value=httpx.Response(200, json=[{"name": "only"}]),
    )
    with Client(api_url="https://api.test", token="tk") as c:
        pages = list(iter_pages(c, "/api/v2/tsig", page_size=50))
    assert pages == [[{"name": "only"}]]


# -------------------------------------------------------------- envelope shape


@respx.mock
def test_envelope_walks_using_last_page_metadata() -> None:
    route = respx.get("https://api.test/api/v2/zones")
    route.side_effect = [
        httpx.Response(
            200,
            json={
                "data": [{"domain": f"z{i}.example."} for i in range(2)],
                "current_page": 1,
                "last_page": 3,
                "per_page": 2,
                "total": 5,
            },
        ),
        httpx.Response(
            200,
            json={
                "data": [{"domain": f"z{i}.example."} for i in range(2, 4)],
                "current_page": 2,
                "last_page": 3,
                "per_page": 2,
                "total": 5,
            },
        ),
        httpx.Response(
            200,
            json={
                "data": [{"domain": "z4.example."}],
                "current_page": 3,
                "last_page": 3,
                "per_page": 2,
                "total": 5,
            },
        ),
    ]
    with Client(api_url="https://api.test", token="tk") as c:
        pages = list(iter_pages(c, "/api/v2/zones", page_size=2))
    assert [row["domain"] for page in pages for row in page] == [
        "z0.example.",
        "z1.example.",
        "z2.example.",
        "z3.example.",
        "z4.example.",
    ]
    assert route.call_count == 3


@respx.mock
def test_envelope_stops_on_empty_data_even_if_last_page_lies() -> None:
    """Safety belt: some APIs report last_page incorrectly; empty data stops us."""
    route = respx.get("https://api.test/api/v2/zones")
    route.side_effect = [
        httpx.Response(
            200,
            json={"data": [{"domain": "only"}], "current_page": 1, "last_page": 99},
        ),
        httpx.Response(
            200,
            json={"data": [], "current_page": 2, "last_page": 99},
        ),
    ]
    with Client(api_url="https://api.test", token="tk") as c:
        rows = list(iter_all(c, "/api/v2/zones", page_size=50))
    assert rows == [{"domain": "only"}]
    assert route.call_count == 2


@respx.mock
def test_envelope_single_page_stops_immediately() -> None:
    respx.get("https://api.test/api/v2/zones").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"domain": "only"}], "current_page": 1, "last_page": 1},
        ),
    )
    with Client(api_url="https://api.test", token="tk") as c:
        pages = list(iter_pages(c, "/api/v2/zones", page_size=50))
    assert pages == [[{"domain": "only"}]]


# --------------------------------------------------------------- iter_all flatten


@respx.mock
def test_iter_all_flattens_bare_array_pages() -> None:
    respx.get("https://api.test/api/v2/tsig").mock(
        side_effect=[
            httpx.Response(200, json=[{"name": "a"}, {"name": "b"}]),
            httpx.Response(200, json=[{"name": "c"}]),
        ],
    )
    with Client(api_url="https://api.test", token="tk") as c:
        rows = list(iter_all(c, "/api/v2/tsig", page_size=2))
    assert [r["name"] for r in rows] == ["a", "b", "c"]


# ------------------------------------------------------------------ error paths


@respx.mock
def test_iter_pages_raises_server_error_on_unexpected_shape() -> None:
    respx.get("https://api.test/api/v2/zones").mock(
        return_value=httpx.Response(200, json={"unexpected": "not a list or envelope"}),
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
        list(
            iter_pages(
                c,
                "/api/v2/zones",
                page_size=2,
                params={"name": "x", "page": 99},
            ),
        )
    assert route.called


# ------------------------------------------------------------------ fetch_page


@respx.mock
def test_fetch_page_envelope_returns_page_info() -> None:
    route = respx.get(
        "https://api.test/api/v2/zones",
        params={"page": 1, "page_size": 50},
    )
    route.mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [{"domain": f"z{i}."} for i in range(50)],
                "current_page": 1,
                "last_page": 3,
                "per_page": 50,
                "total": 137,
            },
        ),
    )
    with Client(api_url="https://api.test", token="tk") as c:
        rows, info = fetch_page(c, "/api/v2/zones", page=1, page_size=50)
    assert len(rows) == 50
    assert info == PageInfo(
        current_page=1,
        last_page=3,
        per_page=50,
        total=137,
        is_envelope=True,
    )
    assert route.call_count == 1


@respx.mock
def test_fetch_page_bare_array_returns_unknown_totals() -> None:
    route = respx.get(
        "https://api.test/api/v2/tsig",
        params={"page": 2, "page_size": 50},
    )
    route.mock(
        return_value=httpx.Response(200, json=[{"name": f"k{i}"} for i in range(50)]),
    )
    with Client(api_url="https://api.test", token="tk") as c:
        rows, info = fetch_page(c, "/api/v2/tsig", page=2, page_size=50)
    assert len(rows) == 50
    assert info.is_envelope is False
    assert info.current_page == 2
    assert info.last_page is None
    assert info.total is None
    assert info.per_page == 50


@respx.mock
def test_fetch_page_envelope_missing_total_is_none() -> None:
    respx.get(
        "https://api.test/api/v2/zones",
        params={"page": 1, "page_size": 50},
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [{"domain": "z."}],
                "current_page": 1,
                "last_page": 1,
                "per_page": 50,
            },
        ),
    )
    with Client(api_url="https://api.test", token="tk") as c:
        _, info = fetch_page(c, "/api/v2/zones", page=1, page_size=50)
    assert info.total is None
    assert info.last_page == 1


def test_fetch_page_rejects_zero_page_size() -> None:
    with (
        Client(api_url="https://api.test", token="tk") as c,
        pytest.raises(ValueError, match="page_size"),
    ):
        fetch_page(c, "/api/v2/zones", page=1, page_size=0)


def test_fetch_page_rejects_zero_page() -> None:
    with (
        Client(api_url="https://api.test", token="tk") as c,
        pytest.raises(ValueError, match="page must be positive"),
    ):
        fetch_page(c, "/api/v2/zones", page=0, page_size=50)


@respx.mock
def test_fetch_page_raises_server_error_on_unexpected_shape() -> None:
    respx.get("https://api.test/api/v2/zones").mock(
        return_value=httpx.Response(200, json={"unexpected": "nope"}),
    )
    with (
        Client(api_url="https://api.test", token="tk") as c,
        pytest.raises(ServerError),
    ):
        fetch_page(c, "/api/v2/zones", page=1, page_size=50)

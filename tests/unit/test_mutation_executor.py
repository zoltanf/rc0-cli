"""Unit tests for execute_mutation."""

from __future__ import annotations

from typing import Any

import httpx
import respx

from rc0.client.dry_run import DryRunResult
from rc0.client.http import Client
from rc0.client.mutations import execute_mutation


def _client() -> Client:
    return Client(api_url="https://my.rcodezero.at", token="tk")


def test_dry_run_returns_dry_run_result() -> None:
    with _client() as client:
        result = execute_mutation(
            client,
            method="POST",
            path="/api/v2/zones",
            body={"domain": "example.com", "type": "master"},
            dry_run=True,
            summary="Would create zone example.com.",
        )
    assert isinstance(result, DryRunResult)
    assert result.request.method == "POST"
    assert result.request.url.endswith("/api/v2/zones")
    assert result.request.headers["Authorization"] == "Bearer tk"
    assert result.request.body == {"domain": "example.com", "type": "master"}


def test_dry_run_inlines_query_params_into_url() -> None:
    with _client() as client:
        result = execute_mutation(
            client,
            method="POST",
            path="/api/v2/zones",
            body={"domain": "example.com", "type": "master"},
            params={"test": 1},
            dry_run=True,
            summary="Would test-validate zone example.com.",
        )
    assert isinstance(result, DryRunResult)
    assert result.request.url.endswith("/api/v2/zones?test=1")


@respx.mock
def test_live_path_parses_json_dict() -> None:
    route = respx.post("https://my.rcodezero.at/api/v2/zones").mock(
        return_value=httpx.Response(201, json={"status": "ok", "id": 42}),
    )
    with _client() as client:
        result = execute_mutation(
            client,
            method="POST",
            path="/api/v2/zones",
            body={"domain": "example.com", "type": "master"},
            dry_run=False,
            summary="Would create zone example.com.",
        )
    assert route.called
    assert result == {"status": "ok", "id": 42}


@respx.mock
def test_live_path_wraps_bare_list() -> None:
    respx.put("https://my.rcodezero.at/api/v2/foo").mock(
        return_value=httpx.Response(200, json=[1, 2, 3]),
    )
    with _client() as client:
        result: Any = execute_mutation(
            client,
            method="PUT",
            path="/api/v2/foo",
            body={},
            dry_run=False,
            summary="fake",
        )
    assert result == {"data": [1, 2, 3]}


def test_dry_run_threads_side_effects() -> None:
    with _client() as client:
        result = execute_mutation(
            client,
            method="POST",
            path="/api/v2/zones",
            body={"domain": "example.com", "type": "master"},
            dry_run=True,
            summary="…",
            side_effects=["creates_zone", "may_create_dnssec_keys"],
        )
    assert isinstance(result, DryRunResult)
    assert result.side_effects == ["creates_zone", "may_create_dnssec_keys"]


@respx.mock
def test_live_path_handles_204_no_content() -> None:
    respx.delete("https://my.rcodezero.at/api/v2/foo").mock(
        return_value=httpx.Response(204),
    )
    with _client() as client:
        result = execute_mutation(
            client,
            method="DELETE",
            path="/api/v2/foo",
            dry_run=False,
            summary="fake",
        )
    assert result == {"status": "ok"}

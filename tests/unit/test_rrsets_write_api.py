"""API wrapper tests for PATCH/PUT/DELETE on /api/v2/zones/{zone}/rrsets."""

from __future__ import annotations

import json

import httpx
import respx

from rc0.api import rrsets_write as api
from rc0.client.dry_run import DryRunResult
from rc0.client.http import Client
from rc0.models.rrset_write import (
    RecordInput,
    RRsetChange,
    RRsetInput,
)


def _client() -> Client:
    return Client(api_url="https://my.rcodezero.at", token="tk")


@respx.mock
def test_patch_rrsets_live() -> None:
    route = respx.patch(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    change = RRsetChange(
        name="www.example.com.",
        type="A",
        ttl=3600,
        changetype="add",
        records=[RecordInput(content="10.0.0.1")],
    )
    with _client() as client:
        result = api.patch_rrsets(
            client,
            zone="example.com",
            changes=[change],
            dry_run=False,
            summary="…",
        )
    assert route.called
    sent = json.loads(route.calls.last.request.content)
    assert sent == [
        {
            "name": "www.example.com.",
            "type": "A",
            "ttl": 3600,
            "changetype": "add",
            "records": [{"content": "10.0.0.1", "disabled": False}],
        },
    ]
    assert result == {"status": "ok"}


def test_patch_rrsets_dry_run() -> None:
    change = RRsetChange(
        name="www.example.com.",
        type="A",
        ttl=3600,
        changetype="add",
        records=[RecordInput(content="10.0.0.1")],
    )
    with _client() as client:
        result = api.patch_rrsets(
            client,
            zone="example.com",
            changes=[change],
            dry_run=True,
            summary="Would add 1 rrset to example.com.",
        )
    assert isinstance(result, DryRunResult)
    assert result.request.method == "PATCH"
    assert result.request.url.endswith("/api/v2/zones/example.com/rrsets")
    assert result.request.body == [
        {
            "name": "www.example.com.",
            "type": "A",
            "ttl": 3600,
            "changetype": "add",
            "records": [{"content": "10.0.0.1", "disabled": False}],
        },
    ]
    assert "example.com" in result.summary


@respx.mock
def test_put_rrsets_live_wraps_in_rrsets_key() -> None:
    route = respx.put(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    rrset = RRsetInput(
        name="www.example.com.",
        type="A",
        ttl=3600,
        records=[RecordInput(content="10.0.0.1")],
    )
    with _client() as client:
        api.put_rrsets(
            client,
            zone="example.com",
            rrsets=[rrset],
            dry_run=False,
            summary="…",
        )
    sent = json.loads(route.calls.last.request.content)
    assert sent == {
        "rrsets": [
            {
                "name": "www.example.com.",
                "type": "A",
                "ttl": 3600,
                "records": [{"content": "10.0.0.1", "disabled": False}],
            },
        ],
    }


def test_put_rrsets_dry_run() -> None:
    rrset = RRsetInput(
        name="www.example.com.",
        type="A",
        ttl=3600,
        records=[RecordInput(content="10.0.0.1")],
    )
    with _client() as client:
        result = api.put_rrsets(
            client,
            zone="example.com",
            rrsets=[rrset],
            dry_run=True,
            summary="Would replace 1 rrset in example.com.",
        )
    assert isinstance(result, DryRunResult)
    assert result.request.method == "PUT"
    assert result.request.body == {
        "rrsets": [
            {
                "name": "www.example.com.",
                "type": "A",
                "ttl": 3600,
                "records": [{"content": "10.0.0.1", "disabled": False}],
            },
        ],
    }


@respx.mock
def test_clear_rrsets_live() -> None:
    route = respx.delete(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(204))
    with _client() as client:
        result = api.clear_rrsets(client, zone="example.com", dry_run=False)
    assert route.called
    assert result == {"status": "ok"}


def test_clear_rrsets_dry_run() -> None:
    with _client() as client:
        result = api.clear_rrsets(client, zone="example.com", dry_run=True)
    assert isinstance(result, DryRunResult)
    assert result.request.method == "DELETE"
    assert result.request.url.endswith("/api/v2/zones/example.com/rrsets")
    assert result.request.body is None
    assert "clear" in result.summary.lower() or "delete" in result.summary.lower()

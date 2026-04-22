"""API wrapper tests for write operations against /api/v2/zones[...]."""

from __future__ import annotations

import httpx
import respx

from rc0.api import zones_write as api
from rc0.client.dry_run import DryRunResult
from rc0.client.http import Client


def _client() -> Client:
    return Client(api_url="https://my.rcodezero.at", token="tk")


@respx.mock
def test_create_zone_live() -> None:
    route = respx.post("https://my.rcodezero.at/api/v2/zones").mock(
        return_value=httpx.Response(201, json={"status": "ok", "domain": "example.com"}),
    )
    with _client() as client:
        result = api.create_zone(
            client,
            domain="example.com",
            zone_type="master",
            dry_run=False,
        )
    assert route.called
    assert route.calls.last.request.read() == b'{"domain":"example.com","type":"master"}'
    assert result == {"status": "ok", "domain": "example.com"}


def test_create_zone_dry_run_omits_null_fields() -> None:
    with _client() as client:
        result = api.create_zone(
            client,
            domain="example.com",
            zone_type="master",
            masters=None,
            dry_run=True,
        )
    assert isinstance(result, DryRunResult)
    assert result.request.body == {"domain": "example.com", "type": "master"}
    assert "example.com" in result.summary


def test_create_zone_dry_run_includes_masters() -> None:
    with _client() as client:
        result = api.create_zone(
            client,
            domain="example.com",
            zone_type="slave",
            masters=["10.0.0.1", "10.0.0.2"],
            dry_run=True,
        )
    assert isinstance(result, DryRunResult)
    assert result.request.body == {
        "domain": "example.com",
        "type": "slave",
        "masters": ["10.0.0.1", "10.0.0.2"],
    }


def test_patch_zone_disabled_dry_run() -> None:
    with _client() as client:
        result = api.patch_zone_disabled(
            client,
            zone="example.com",
            disabled=True,
            dry_run=True,
        )
    assert isinstance(result, DryRunResult)
    assert result.request.body == {"zone_disabled": True}
    assert "disable" in result.summary.lower()


def test_test_zone_dry_run_adds_test_query() -> None:
    with _client() as client:
        result = api.test_zone(
            client,
            domain="example.com",
            zone_type="master",
            dry_run=True,
        )
    assert isinstance(result, DryRunResult)
    assert result.request.url.endswith("/api/v2/zones?test=1")


@respx.mock
def test_delete_zone_live() -> None:
    respx.delete("https://my.rcodezero.at/api/v2/zones/example.com").mock(
        return_value=httpx.Response(204),
    )
    with _client() as client:
        result = api.delete_zone(client, zone="example.com", dry_run=False)
    assert result == {"status": "ok"}


@respx.mock
def test_retrieve_zone_live() -> None:
    respx.post("https://my.rcodezero.at/api/v2/zones/example.com/retrieve").mock(
        return_value=httpx.Response(200, json={"status": "ok"}),
    )
    with _client() as client:
        result = api.retrieve_zone(client, zone="example.com", dry_run=False)
    assert result == {"status": "ok"}


@respx.mock
def test_set_inbound_live_posts_tsigkey() -> None:
    route = respx.post("https://my.rcodezero.at/api/v2/zones/example.com/inbound").mock(
        return_value=httpx.Response(200, json={"tsigkey": "k"}),
    )
    with _client() as client:
        api.set_inbound(client, zone="example.com", tsigkey="k", dry_run=False)
    assert route.called
    assert route.calls.last.request.read() == b'{"tsigkey":"k"}'


@respx.mock
def test_unset_outbound_live_issues_delete() -> None:
    route = respx.delete("https://my.rcodezero.at/api/v2/zones/example.com/outbound").mock(
        return_value=httpx.Response(204),
    )
    with _client() as client:
        api.unset_outbound(client, zone="example.com", dry_run=False)
    assert route.called


def test_set_outbound_dry_run_serialises_secondaries_and_tsigkey() -> None:
    with _client() as client:
        result = api.set_outbound(
            client,
            zone="example.com",
            secondaries=["10.0.0.1"],
            tsigkey="k",
            dry_run=True,
        )
    assert isinstance(result, DryRunResult)
    assert result.request.body == {"secondaries": ["10.0.0.1"], "tsigkey": "k"}

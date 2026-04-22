"""Unit tests for DNSSEC API wrappers."""

from __future__ import annotations

import httpx
import respx

from rc0.api import dnssec_write as api
from rc0.client.dry_run import DryRunResult
from rc0.client.http import Client


def _client() -> Client:
    return Client(api_url="https://my.rcodezero.at", token="tk")


# ------------------------------------------------------------------ sign_zone


@respx.mock
def test_sign_zone_live_no_params() -> None:
    route = respx.post("https://my.rcodezero.at/api/v2/zones/example.com/sign").mock(
        return_value=httpx.Response(200, json={"status": "ok"}),
    )
    with _client() as client:
        result = api.sign_zone(client, zone="example.com", dry_run=False)
    assert route.called
    assert result == {"status": "ok"}
    assert "ignoresafetyperiod" not in str(route.calls.last.request.url)
    assert "enable_cds_cdnskey" not in str(route.calls.last.request.url)


@respx.mock
def test_sign_zone_live_with_params() -> None:
    route = respx.post("https://my.rcodezero.at/api/v2/zones/example.com/sign").mock(
        return_value=httpx.Response(200, json={"status": "ok"}),
    )
    with _client() as client:
        api.sign_zone(
            client,
            zone="example.com",
            ignore_safety_period=True,
            enable_cds_cdnskey=True,
            dry_run=False,
        )
    url = str(route.calls.last.request.url)
    assert "ignoresafetyperiod=1" in url
    assert "enable_cds_cdnskey=1" in url


def test_sign_zone_dry_run() -> None:
    with _client() as client:
        result = api.sign_zone(client, zone="example.com", dry_run=True)
    assert isinstance(result, DryRunResult)
    assert result.request.method == "POST"
    assert result.request.url.endswith("/api/v2/zones/example.com/sign")
    assert result.request.body is None


def test_sign_zone_dry_run_with_params() -> None:
    with _client() as client:
        result = api.sign_zone(
            client,
            zone="example.com",
            ignore_safety_period=True,
            dry_run=True,
        )
    assert isinstance(result, DryRunResult)
    assert "ignoresafetyperiod=1" in result.request.url


# ---------------------------------------------------------------- unsign_zone


@respx.mock
def test_unsign_zone_live() -> None:
    route = respx.post("https://my.rcodezero.at/api/v2/zones/example.com/unsign").mock(
        return_value=httpx.Response(200, json={"status": "ok"}),
    )
    with _client() as client:
        result = api.unsign_zone(client, zone="example.com", dry_run=False)
    assert route.called
    assert result == {"status": "ok"}


def test_unsign_zone_dry_run() -> None:
    with _client() as client:
        result = api.unsign_zone(client, zone="example.com", dry_run=True)
    assert isinstance(result, DryRunResult)
    assert result.request.method == "POST"
    assert result.request.url.endswith("/api/v2/zones/example.com/unsign")


# --------------------------------------------------------------- keyrollover


@respx.mock
def test_keyrollover_live() -> None:
    route = respx.post(
        "https://my.rcodezero.at/api/v2/zones/example.com/keyrollover",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    with _client() as client:
        result = api.keyrollover(client, zone="example.com", dry_run=False)
    assert route.called
    assert result == {"status": "ok"}


def test_keyrollover_dry_run() -> None:
    with _client() as client:
        result = api.keyrollover(client, zone="example.com", dry_run=True)
    assert isinstance(result, DryRunResult)
    assert result.request.url.endswith("/api/v2/zones/example.com/keyrollover")


# -------------------------------------------------------------------- ack_ds


@respx.mock
def test_ack_ds_live() -> None:
    route = respx.post(
        "https://my.rcodezero.at/api/v2/zones/example.com/dsupdate",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    with _client() as client:
        result = api.ack_ds(client, zone="example.com", dry_run=False)
    assert route.called
    assert result == {"status": "ok"}


def test_ack_ds_dry_run() -> None:
    with _client() as client:
        result = api.ack_ds(client, zone="example.com", dry_run=True)
    assert isinstance(result, DryRunResult)
    assert result.request.url.endswith("/api/v2/zones/example.com/dsupdate")


# ---------------------------------------------------------- simulate_dsseen


@respx.mock
def test_simulate_dsseen_live() -> None:
    route = respx.post(
        "https://my.rcodezero.at/api/v2/zones/example.com/simulate/dsseen",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    with _client() as client:
        result = api.simulate_dsseen(client, zone="example.com", dry_run=False)
    assert route.called
    assert result == {"status": "ok"}


def test_simulate_dsseen_dry_run() -> None:
    with _client() as client:
        result = api.simulate_dsseen(client, zone="example.com", dry_run=True)
    assert isinstance(result, DryRunResult)
    assert result.request.url.endswith("/api/v2/zones/example.com/simulate/dsseen")


# -------------------------------------------------------- simulate_dsremoved


@respx.mock
def test_simulate_dsremoved_live() -> None:
    route = respx.post(
        "https://my.rcodezero.at/api/v2/zones/example.com/simulate/dsremoved",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    with _client() as client:
        result = api.simulate_dsremoved(client, zone="example.com", dry_run=False)
    assert route.called
    assert result == {"status": "ok"}


def test_simulate_dsremoved_dry_run() -> None:
    with _client() as client:
        result = api.simulate_dsremoved(client, zone="example.com", dry_run=True)
    assert isinstance(result, DryRunResult)
    assert result.request.url.endswith("/api/v2/zones/example.com/simulate/dsremoved")

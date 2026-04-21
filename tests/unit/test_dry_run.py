"""Tests for the dry-run request capture and renderer."""

from __future__ import annotations

from rc0.client.dry_run import build_dry_run
from rc0.client.http import REDACTED, Client


def test_dry_run_shape_and_redaction() -> None:
    client = Client(api_url="https://api.test", token="s3cret")
    try:
        result = build_dry_run(
            client,
            method="POST",
            path="/api/v2/zones",
            body={"domain": "example.com", "type": "master"},
            summary="Would create master zone example.com.",
            side_effects=["creates_zone"],
        )
    finally:
        client.close()
    body = result.to_dict()
    assert body["dry_run"] is True
    assert body["request"]["method"] == "POST"
    assert body["request"]["url"] == "https://api.test/api/v2/zones"
    assert body["request"]["headers"]["Authorization"] == f"Bearer {REDACTED}"
    assert body["request"]["headers"]["Content-Type"] == "application/json"
    assert body["request"]["body"] == {"domain": "example.com", "type": "master"}
    assert body["summary"] == "Would create master zone example.com."
    assert body["side_effects"] == ["creates_zone"]


def test_dry_run_no_body_omits_content_type() -> None:
    client = Client(api_url="https://api.test", token="tk")
    try:
        result = build_dry_run(
            client,
            method="DELETE",
            path="/api/v2/zones/example.com",
            summary="Would delete zone example.com.",
        )
    finally:
        client.close()
    headers = result.to_dict()["request"]["headers"]
    assert "Content-Type" not in headers


def test_build_dry_run_appends_params() -> None:
    client = Client(api_url="https://api.test", token="tk")
    try:
        result = build_dry_run(
            client,
            method="POST",
            path="/api/v2/zones",
            params={"test": 1},
            summary="Would test-validate zone.",
        )
    finally:
        client.close()
    assert result.request.url.endswith("?test=1")

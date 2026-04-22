"""Dry-run vs. live request parity for every Phase-2 and Phase-3 mutation."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import httpx
import pytest
import respx
from typer.testing import CliRunner

from rc0.app import app

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def cli() -> CliRunner:
    return CliRunner()


@pytest.fixture
def changes_yaml_path(tmp_path: Path) -> Path:
    """Minimal PATCH-shape changes file; shared between dry-run and live."""
    p = tmp_path / "changes.yaml"
    p.write_text(
        "- name: www.example.com.\n"
        "  type: A\n"
        "  ttl: 3600\n"
        "  changetype: add\n"
        "  records:\n"
        "    - content: 10.0.0.1\n",
    )
    return p


@pytest.fixture
def replacement_yaml_path(tmp_path: Path) -> Path:
    p = tmp_path / "replacement.yaml"
    p.write_text(
        "- name: www.example.com.\n  type: A\n  ttl: 3600\n  records:\n    - content: 10.0.0.1\n",
    )
    return p


# (method, url, args, mock-status, mock-body)
PARITY_CASES: list[tuple[str, str, list[str], int, Any]] = [
    (
        "POST",
        "https://my.rcodezero.at/api/v2/zones",
        ["zone", "create", "example.com", "--type", "master", "--master", "10.0.0.1"],
        201,
        {"status": "ok"},
    ),
    (
        "PUT",
        "https://my.rcodezero.at/api/v2/zones/example.com",
        ["zone", "update", "example.com", "--master", "10.0.0.2"],
        200,
        {"status": "ok"},
    ),
    (
        "PATCH",
        "https://my.rcodezero.at/api/v2/zones/example.com",
        ["zone", "enable", "example.com"],
        200,
        {"status": "ok"},
    ),
    (
        "PATCH",
        "https://my.rcodezero.at/api/v2/zones/example.com",
        ["zone", "disable", "example.com"],
        200,
        {"status": "ok"},
    ),
    (
        "DELETE",
        "https://my.rcodezero.at/api/v2/zones/example.com",
        ["-y", "zone", "delete", "example.com"],
        204,
        None,
    ),
    (
        "POST",
        "https://my.rcodezero.at/api/v2/zones/example.com/retrieve",
        ["zone", "retrieve", "example.com"],
        200,
        {"status": "ok"},
    ),
    (
        "POST",
        "https://my.rcodezero.at/api/v2/zones/example.com/inbound",
        ["zone", "xfr-in", "set", "example.com", "--tsigkey", "k"],
        200,
        {"status": "ok"},
    ),
    (
        "DELETE",
        "https://my.rcodezero.at/api/v2/zones/example.com/inbound",
        ["zone", "xfr-in", "unset", "example.com"],
        204,
        None,
    ),
    (
        "POST",
        "https://my.rcodezero.at/api/v2/zones/example.com/outbound",
        ["zone", "xfr-out", "set", "example.com", "--tsigkey", "k", "--secondary", "10.0.0.1"],
        200,
        {"status": "ok"},
    ),
    (
        "DELETE",
        "https://my.rcodezero.at/api/v2/zones/example.com/outbound",
        ["zone", "xfr-out", "unset", "example.com"],
        204,
        None,
    ),
    (
        "POST",
        "https://my.rcodezero.at/api/v2/tsig",
        ["tsig", "add", "k1", "--algorithm", "hmac-sha256", "--secret", "abc"],
        201,
        {"status": "ok"},
    ),
    (
        "PUT",
        "https://my.rcodezero.at/api/v2/tsig/k1",
        ["tsig", "update", "k1", "--algorithm", "hmac-sha512", "--secret", "xyz"],
        200,
        {"status": "ok"},
    ),
    (
        "DELETE",
        "https://my.rcodezero.at/api/v2/tsig/k1",
        ["-y", "tsig", "delete", "k1"],
        204,
        None,
    ),
    (
        "PUT",
        "https://my.rcodezero.at/api/v2/settings/secondaries",
        ["settings", "secondaries", "set", "--ip", "10.0.0.1"],
        200,
        {"status": "ok"},
    ),
    (
        "DELETE",
        "https://my.rcodezero.at/api/v2/settings/secondaries",
        ["settings", "secondaries", "unset"],
        204,
        None,
    ),
    (
        "PUT",
        "https://my.rcodezero.at/api/v2/settings/tsig/in",
        ["settings", "tsig-in", "set", "k1"],
        200,
        {"status": "ok"},
    ),
    (
        "DELETE",
        "https://my.rcodezero.at/api/v2/settings/tsig/in",
        ["settings", "tsig-in", "unset"],
        204,
        None,
    ),
    (
        "PUT",
        "https://my.rcodezero.at/api/v2/settings/tsig/out",
        ["settings", "tsig-out", "set", "k1"],
        200,
        {"status": "ok"},
    ),
    (
        "DELETE",
        "https://my.rcodezero.at/api/v2/settings/tsig/out",
        ["settings", "tsig-out", "unset"],
        204,
        None,
    ),
    (
        "DELETE",
        "https://my.rcodezero.at/api/v2/messages/7",
        ["messages", "ack", "7"],
        204,
        None,
    ),
    # --- Phase 3 ---
    (
        "PATCH",
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
        [
            "record",
            "add",
            "example.com",
            "--name",
            "www.example.com.",
            "--type",
            "A",
            "--content",
            "10.0.0.1",
        ],
        200,
        {"status": "ok"},
    ),
    (
        "PATCH",
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
        [
            "record",
            "update",
            "example.com",
            "--name",
            "www.example.com.",
            "--type",
            "A",
            "--content",
            "10.0.0.2",
        ],
        200,
        {"status": "ok"},
    ),
    (
        "PATCH",
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
        [
            "-y",
            "record",
            "delete",
            "example.com",
            "--name",
            "www.example.com.",
            "--type",
            "A",
        ],
        200,
        {"status": "ok"},
    ),
    (
        "DELETE",
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
        ["-y", "record", "clear", "example.com"],
        204,
        None,
    ),
    # --- Phase 4 ---
    (
        "POST",
        "https://my.rcodezero.at/api/v2/zones/example.com/sign",
        ["dnssec", "sign", "example.com"],
        200,
        {"status": "ok"},
    ),
    (
        "POST",
        "https://my.rcodezero.at/api/v2/zones/example.com/unsign",
        ["-y", "dnssec", "unsign", "example.com", "--force"],
        200,
        {"status": "ok"},
    ),
    (
        "POST",
        "https://my.rcodezero.at/api/v2/zones/example.com/keyrollover",
        ["-y", "dnssec", "keyrollover", "example.com"],
        200,
        {"status": "ok"},
    ),
    (
        "POST",
        "https://my.rcodezero.at/api/v2/zones/example.com/dsupdate",
        ["dnssec", "ack-ds", "example.com"],
        200,
        {"status": "ok"},
    ),
    # --- Phase 5 ---
    (
        "PATCH",
        "https://my.rcodezero.at/api/v1/acme/zones/example.com/rrsets",
        ["acme", "add-challenge", "example.com", "--value", "mytoken"],
        200,
        {"status": "ok"},
    ),
    (
        "PATCH",
        "https://my.rcodezero.at/api/v1/acme/zones/example.com/rrsets",
        ["-y", "acme", "remove-challenge", "example.com"],
        200,
        {"status": "ok"},
    ),
]


@pytest.mark.parametrize(
    ("method", "url", "args", "status", "body"),
    PARITY_CASES,
    ids=[" ".join(c[2]) for c in PARITY_CASES],
)
@respx.mock
def test_dry_run_parity(
    cli: CliRunner,
    isolated_config: Path,
    method: str,
    url: str,
    args: list[str],
    status: int,
    body: Any,
) -> None:
    # 1. Dry-run: capture what we would send.
    dry = cli.invoke(
        app,
        ["--token", "tk", "-o", "json", "--dry-run", *args],
    )
    assert dry.exit_code == 0, dry.stdout
    dry_payload = json.loads(dry.stdout)
    dry_req = dry_payload["request"]

    # 2. Live: mock the exact URL and method, invoke the same args.
    respx.request(method, url).mock(
        return_value=httpx.Response(
            status,
            json=body if body is not None else {},
        )
    )
    live = cli.invoke(app, ["--token", "tk", "-o", "json", *args])
    assert live.exit_code == 0, live.stdout
    live_request = respx.calls.last.request

    # 3. Compare: method, URL (path+query), JSON body.
    assert dry_req["method"] == method
    assert live_request.method == method
    assert dry_req["url"] == str(live_request.url)
    dry_body = dry_req.get("body")
    live_body = json.loads(live_request.content) if live_request.content else None
    assert dry_body == live_body


@respx.mock
def test_dry_run_parity_record_apply(
    cli: CliRunner,
    isolated_config: Path,
    changes_yaml_path: Path,
) -> None:
    args = [
        "-y",
        "record",
        "apply",
        "example.com",
        "--from-file",
        str(changes_yaml_path),
    ]
    dry = cli.invoke(app, ["--token", "tk", "-o", "json", "--dry-run", *args])
    assert dry.exit_code == 0, dry.stdout
    dry_req = json.loads(dry.stdout)["request"]

    respx.patch(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    live = cli.invoke(app, ["--token", "tk", "-o", "json", *args])
    assert live.exit_code == 0, live.stdout
    live_req = respx.calls.last.request
    assert dry_req["method"] == "PATCH"
    assert dry_req["url"] == str(live_req.url)
    assert dry_req["body"] == json.loads(live_req.content)


@respx.mock
def test_dry_run_parity_record_replace_all(
    cli: CliRunner,
    isolated_config: Path,
    replacement_yaml_path: Path,
) -> None:
    args = [
        "-y",
        "record",
        "replace-all",
        "example.com",
        "--from-file",
        str(replacement_yaml_path),
    ]
    dry = cli.invoke(app, ["--token", "tk", "-o", "json", "--dry-run", *args])
    assert dry.exit_code == 0, dry.stdout
    dry_req = json.loads(dry.stdout)["request"]

    respx.put(
        "https://my.rcodezero.at/api/v2/zones/example.com/rrsets",
    ).mock(return_value=httpx.Response(200, json={"status": "ok"}))
    live = cli.invoke(app, ["--token", "tk", "-o", "json", *args])
    assert live.exit_code == 0, live.stdout
    live_req = respx.calls.last.request
    assert dry_req["method"] == "PUT"
    assert dry_req["url"] == str(live_req.url)
    assert dry_req["body"] == json.loads(live_req.content)

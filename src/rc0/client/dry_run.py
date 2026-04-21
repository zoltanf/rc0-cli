"""Capture the HTTP request a mutation *would* have made, and render it.

Mission plan §7: every state-changing command supports ``--dry-run``. Dry-run
produces **no** HTTP mutation and exits 0.

JSON shape::

    {
      "dry_run": true,
      "request": {
        "method": "...",
        "url": "...",
        "headers": {...},
        "body": {...}
      },
      "summary": "...",
      "side_effects": [...]
    }
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from rc0.client.http import Client

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass
class DryRunRequest:
    """A fully-rendered would-be HTTP request."""

    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    body: Any = None

    def to_dict(self, *, redact: bool = True) -> dict[str, Any]:
        headers: Mapping[str, str] = (
            Client.redact_headers(self.headers) if redact else dict(self.headers)
        )
        out: dict[str, Any] = {
            "method": self.method.upper(),
            "url": self.url,
            "headers": dict(headers),
        }
        if self.body is not None:
            out["body"] = self.body
        return out


@dataclass
class DryRunResult:
    """What a mutation command returns when ``--dry-run`` is set."""

    request: DryRunRequest
    summary: str
    side_effects: list[str] = field(default_factory=list)

    def to_dict(self, *, redact: bool = True) -> dict[str, Any]:
        return {
            "dry_run": True,
            "request": self.request.to_dict(redact=redact),
            "summary": self.summary,
            "side_effects": list(self.side_effects),
        }


def build_dry_run(
    client: Client,
    *,
    method: str,
    path: str,
    body: Any = None,
    summary: str,
    side_effects: list[str] | None = None,
    extra_headers: Mapping[str, str] | None = None,
) -> DryRunResult:
    """Assemble a DryRunResult mirroring what ``client.request`` would send."""
    headers: dict[str, str] = {}
    if client.token is not None:
        headers["Authorization"] = f"Bearer {client.token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
    if extra_headers:
        headers.update(extra_headers)

    url = path if path.startswith("http") else f"{client.api_url.rstrip('/')}{path}"
    return DryRunResult(
        request=DryRunRequest(
            method=method,
            url=url,
            headers=headers,
            body=body,
        ),
        summary=summary,
        side_effects=list(side_effects or []),
    )

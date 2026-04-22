"""Tests for rc0.rrsets.parse.from_file (JSON / YAML)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from rc0.client.errors import ValidationError
from rc0.rrsets.parse import from_file

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def _warn_sink() -> tuple[list[str], Callable[[str], None]]:
    captured: list[str] = []
    return captured, captured.append


def test_from_file_yaml(tmp_path: Path) -> None:
    src = tmp_path / "changes.yaml"
    src.write_text(
        """- name: www.example.com.
  type: A
  ttl: 3600
  changetype: add
  records:
    - content: 10.0.0.1
    - content: 10.0.0.2
- name: old.example.com.
  type: A
  ttl: 3600
  changetype: delete
""",
    )
    _, sink = _warn_sink()
    changes = from_file(src, zone="example.com", verbose=0, warn=sink)
    assert len(changes) == 2
    assert changes[0].changetype == "add"
    assert [r.content for r in changes[0].records] == ["10.0.0.1", "10.0.0.2"]
    assert changes[1].changetype == "delete"
    assert changes[1].records == []


def test_from_file_json(tmp_path: Path) -> None:
    src = tmp_path / "changes.json"
    src.write_text(
        """[
  {"name": "www.example.com.", "type": "A", "ttl": 3600,
   "changetype": "add", "records": [{"content": "10.0.0.1"}]}
]""",
    )
    _, sink = _warn_sink()
    changes = from_file(src, zone="example.com", verbose=0, warn=sink)
    assert len(changes) == 1
    assert changes[0].records[0].content == "10.0.0.1"


def test_from_file_qualifies_relative_names_and_warns(tmp_path: Path) -> None:
    src = tmp_path / "changes.yaml"
    src.write_text(
        "- name: www\n  type: A\n  ttl: 3600\n  changetype: add\n"
        "  records:\n    - content: 10.0.0.1\n",
    )
    captured, sink = _warn_sink()
    changes = from_file(src, zone="example.com", verbose=1, warn=sink)
    assert changes[0].name == "www.example.com."
    assert any("www.example.com." in line for line in captured)


def test_from_file_rejects_top_level_dict(tmp_path: Path) -> None:
    src = tmp_path / "wrong.yaml"
    src.write_text("name: www.example.com.\ntype: A\n")
    _, sink = _warn_sink()
    with pytest.raises(ValidationError) as exc:
        from_file(src, zone="example.com", verbose=0, warn=sink)
    assert "list" in exc.value.message.lower()


def test_from_file_unknown_extension(tmp_path: Path) -> None:
    src = tmp_path / "changes.txt"
    src.write_text("[]")
    _, sink = _warn_sink()
    with pytest.raises(ValidationError) as exc:
        from_file(src, zone="example.com", verbose=0, warn=sink)
    assert "extension" in exc.value.message.lower()


def test_from_file_missing_required_field(tmp_path: Path) -> None:
    src = tmp_path / "bad.yaml"
    src.write_text("- name: x\n  type: A\n  changetype: add\n")  # no ttl
    _, sink = _warn_sink()
    with pytest.raises(ValidationError):
        from_file(src, zone="example.com", verbose=0, warn=sink)


def test_from_file_unknown_field_rejected(tmp_path: Path) -> None:
    # Rc0WriteModel extra="forbid" must survive through the parser.
    src = tmp_path / "typo.yaml"
    src.write_text(
        "- name: www.example.com.\n  type: A\n  ttl: 3600\n"
        "  changetype: add\n  records: []\n  note: typo\n",
    )
    _, sink = _warn_sink()
    with pytest.raises(ValidationError):
        from_file(src, zone="example.com", verbose=0, warn=sink)

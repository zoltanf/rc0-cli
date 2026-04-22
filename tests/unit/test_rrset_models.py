"""Tests for Phase-3 RRset request models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from rc0.models.rrset_write import (
    CNAME_CONFLICT_TYPES,
    MIN_TTL,
    PATCH_MAX_RRSETS,
    PUT_MAX_RRSETS,
    RecordInput,
    ReplaceRRsetBody,
    RRsetChange,
    RRsetInput,
)


def test_limit_constants_match_mission_plan() -> None:
    assert PATCH_MAX_RRSETS == 1000
    assert PUT_MAX_RRSETS == 3000
    assert MIN_TTL == 60


def test_cname_conflict_types_includes_core_rr_types() -> None:
    for t in ("A", "AAAA", "MX", "TXT", "NS", "SRV"):
        assert t in CNAME_CONFLICT_TYPES
    assert "CNAME" not in CNAME_CONFLICT_TYPES


def test_rrset_change_roundtrips() -> None:
    change = RRsetChange(
        name="www.example.com.",
        type="A",
        ttl=3600,
        changetype="add",
        records=[RecordInput(content="10.0.0.1")],
    )
    assert change.model_dump() == {
        "name": "www.example.com.",
        "type": "A",
        "ttl": 3600,
        "changetype": "add",
        "records": [{"content": "10.0.0.1", "disabled": False}],
    }


def test_rrset_change_delete_allows_empty_records() -> None:
    change = RRsetChange(
        name="old.example.com.",
        type="A",
        ttl=3600,
        changetype="delete",
    )
    assert change.records == []


def test_rrset_change_rejects_unknown_changetype() -> None:
    with pytest.raises(PydanticValidationError):
        RRsetChange(
            name="x.example.com.",
            type="A",
            ttl=3600,
            changetype="replace",  # type: ignore[arg-type]
        )


def test_rrset_change_rejects_extra_fields() -> None:
    # Rc0WriteModel has extra="forbid"; typos fail loudly.
    with pytest.raises(PydanticValidationError):
        RRsetChange(
            name="x.example.com.",
            type="A",
            ttl=3600,
            changetype="add",
            note="this field does not belong",  # type: ignore[call-arg]
        )


def test_rrset_input_shape_matches_put_body_row() -> None:
    row = RRsetInput(
        name="example.com.",
        type="MX",
        ttl=3600,
        records=[RecordInput(content="10 mail.example.com.")],
    )
    # PUT body rows never carry `changetype`.
    assert "changetype" not in row.model_dump()


def test_replace_rrset_body_roundtrips() -> None:
    body = ReplaceRRsetBody(
        rrsets=[
            RRsetInput(
                name="example.com.",
                type="SOA",
                ttl=3600,
                records=[
                    RecordInput(
                        content="ns1.example.com. admin.example.com. 1 7200 3600 1209600 3600",
                    ),
                ],
            ),
        ],
    )
    dumped = body.model_dump()
    assert "rrsets" in dumped
    assert dumped["rrsets"][0]["type"] == "SOA"

"""Tests for rc0.validation.rrsets."""

from __future__ import annotations

import pytest

from rc0.client.errors import ValidationError
from rc0.models.rrset_write import (
    PATCH_MAX_RRSETS,
    PUT_MAX_RRSETS,
    RecordInput,
    RRsetChange,
    RRsetInput,
)
from rc0.validation.rrsets import (
    enforce_cname_exclusivity,
    enforce_cname_exclusivity_replacement,
    qualify_name,
    validate_changes,
    validate_content_for_type,
    validate_replacement,
    validate_ttl,
)


def test_qualify_name_relative_gets_zone_appended() -> None:
    out, rewritten = qualify_name("www", zone="example.com")
    assert out == "www.example.com."
    assert rewritten is True


def test_qualify_name_at_means_apex() -> None:
    out, rewritten = qualify_name("@", zone="example.com")
    assert out == "example.com."
    assert rewritten is True


def test_qualify_name_absolute_without_dot_gets_dot() -> None:
    out, rewritten = qualify_name("www.example.com", zone="example.com")
    assert out == "www.example.com."
    assert rewritten is True


def test_qualify_name_already_absolute_noop() -> None:
    out, rewritten = qualify_name("www.example.com.", zone="example.com")
    assert out == "www.example.com."
    assert rewritten is False


def test_qualify_name_zone_with_trailing_dot_accepted() -> None:
    out, rewritten = qualify_name("www", zone="example.com.")
    assert out == "www.example.com."
    assert rewritten is True


def test_qualify_name_rejects_empty() -> None:
    with pytest.raises(ValidationError):
        qualify_name("", zone="example.com")


def test_qualify_name_zone_apex_without_dot_gets_dot() -> None:
    out, rewritten = qualify_name("example.com", zone="example.com")
    assert out == "example.com."
    assert rewritten is True


def test_qualify_name_label_prefixed_substring_treated_as_unrelated() -> None:
    # "badexample.com" does NOT end at a label boundary inside "example.com" zone.
    # Must be treated as out-of-zone and fully qualified under the zone.
    out, rewritten = qualify_name("badexample.com", zone="example.com")
    assert out == "badexample.com.example.com."
    assert rewritten is True


def test_validate_ttl_below_floor_raises() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_ttl(30, context="www.example.com. A")
    assert "60" in exc.value.message


def test_validate_ttl_at_floor_ok() -> None:
    validate_ttl(60, context="x")


def test_validate_content_a_accepts_ipv4() -> None:
    validate_content_for_type("A", "10.0.0.1", name="www.example.com.")


def test_validate_content_a_rejects_non_ipv4() -> None:
    with pytest.raises(ValidationError):
        validate_content_for_type("A", "not-an-ip", name="www.example.com.")
    with pytest.raises(ValidationError):
        validate_content_for_type("A", "2001:db8::1", name="www.example.com.")


def test_validate_content_aaaa_accepts_ipv6() -> None:
    validate_content_for_type("AAAA", "2001:db8::1", name="www.example.com.")


def test_validate_content_aaaa_rejects_ipv4() -> None:
    with pytest.raises(ValidationError):
        validate_content_for_type("AAAA", "10.0.0.1", name="www.example.com.")


def test_validate_content_mx_requires_priority() -> None:
    validate_content_for_type("MX", "10 mail.example.com.", name="example.com.")
    with pytest.raises(ValidationError):
        validate_content_for_type("MX", "mail.example.com.", name="example.com.")
    with pytest.raises(ValidationError):
        validate_content_for_type("MX", "high mail.example.com.", name="example.com.")


def test_validate_content_mx_rejects_out_of_range_priority() -> None:
    with pytest.raises(ValidationError):
        validate_content_for_type(
            "MX",
            "99999 mail.example.com.",
            name="example.com.",
        )


def test_enforce_cname_exclusivity_rejects_conflict() -> None:
    changes = [
        RRsetChange(
            name="www.example.com.",
            type="CNAME",
            ttl=3600,
            changetype="add",
            records=[RecordInput(content="host.example.com.")],
        ),
        RRsetChange(
            name="www.example.com.",
            type="A",
            ttl=3600,
            changetype="add",
            records=[RecordInput(content="10.0.0.1")],
        ),
    ]
    with pytest.raises(ValidationError) as exc:
        enforce_cname_exclusivity(changes)
    assert "CNAME" in exc.value.message


def test_enforce_cname_exclusivity_allows_delete_of_other_type() -> None:
    # Moving a label from A to CNAME in a single PATCH should be allowed when
    # the existing A is deleted in the same batch.
    changes = [
        RRsetChange(
            name="www.example.com.",
            type="A",
            ttl=3600,
            changetype="delete",
        ),
        RRsetChange(
            name="www.example.com.",
            type="CNAME",
            ttl=3600,
            changetype="add",
            records=[RecordInput(content="host.example.com.")],
        ),
    ]
    enforce_cname_exclusivity(changes)


def test_validate_changes_enforces_patch_limit() -> None:
    many = [
        RRsetChange(
            name=f"n{i}.example.com.",
            type="A",
            ttl=3600,
            changetype="add",
            records=[RecordInput(content="10.0.0.1")],
        )
        for i in range(PATCH_MAX_RRSETS + 1)
    ]
    with pytest.raises(ValidationError) as exc:
        validate_changes(many)
    assert "1000" in exc.value.message


def test_validate_replacement_enforces_put_limit() -> None:
    many = [
        RRsetInput(
            name=f"n{i}.example.com.",
            type="A",
            ttl=3600,
            records=[RecordInput(content="10.0.0.1")],
        )
        for i in range(PUT_MAX_RRSETS + 1)
    ]
    with pytest.raises(ValidationError) as exc:
        validate_replacement(many)
    assert "3000" in exc.value.message


def test_validate_changes_runs_per_change_validators() -> None:
    changes = [
        RRsetChange(
            name="www.example.com.",
            type="A",
            ttl=10,
            changetype="add",
            records=[RecordInput(content="10.0.0.1")],
        ),
    ]
    with pytest.raises(ValidationError):
        validate_changes(changes)


def test_validate_changes_delete_skips_content_validation() -> None:
    # A delete with no records shouldn't trip IP validation.
    changes = [
        RRsetChange(
            name="www.example.com.",
            type="A",
            ttl=3600,
            changetype="delete",
        ),
    ]
    validate_changes(changes)


def test_enforce_cname_exclusivity_replacement_rejects_conflict() -> None:
    rrsets = [
        RRsetInput(
            name="www.example.com.",
            type="CNAME",
            ttl=3600,
            records=[RecordInput(content="host.example.com.")],
        ),
        RRsetInput(
            name="www.example.com.",
            type="A",
            ttl=3600,
            records=[RecordInput(content="10.0.0.1")],
        ),
    ]
    with pytest.raises(ValidationError):
        enforce_cname_exclusivity_replacement(rrsets)

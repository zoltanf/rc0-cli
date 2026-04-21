"""Report row models — one class per distinct row shape.

The report endpoints return either a Laravel pagination envelope
(``/reports/problematiczones``) or a bare JSON array of row objects. All
models inherit from :class:`Rc0Model`, which sets ``extra="allow"`` so any
fields returned by the API (and not declared here) flow through
``model_dump`` unchanged.

Endpoints whose spec has no usable example are modelled as empty
subclasses — they accept any shape and render every field via extras.
"""

from __future__ import annotations

from rc0.models.common import Rc0Model


class ProblematicZone(Rc0Model):
    """Row from /api/v2/reports/problematiczones. Spec has no usable example."""


class NxdomainRow(Rc0Model):
    """One NXDOMAIN event. API: /api/v2/reports/nxdomains."""

    date: str | None = None
    domain: str | None = None
    qname: str | None = None
    qtype: str | None = None
    querycount: int | None = None


class AccountingRow(Rc0Model):
    """One month of account activity. API: /api/v2/reports/accounting."""

    account: str | None = None
    date: str | None = None
    domain_count: int | None = None
    domain_count_dnssec: int | None = None
    query_count: int | None = None
    records_count: int | None = None


class QueryRateRow(Rc0Model):
    """One day of per-zone query rates. API: /api/v2/reports/queryrates."""

    date: str | None = None
    domain: str | None = None
    nx_querycount: int | None = None
    querycount: int | None = None


class DomainListRow(Rc0Model):
    """One row of the account-wide domain list. API: /api/v2/reports/domainlist."""

    domain: str | None = None
    serial: int | None = None

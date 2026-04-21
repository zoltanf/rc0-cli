"""Placeholder for auto-pagination.

The full iterator ships in Phase 1 (read-only commands). For v0.1.0 we only
need the shape that other modules can import.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Page:
    """A single page of results from a paginated endpoint."""

    items: list[dict[str, object]]
    page: int
    page_size: int
    total: int | None = None


def has_next(page: Page) -> bool:
    """True if another page likely exists."""
    if page.total is None:
        return len(page.items) == page.page_size
    return (page.page * page.page_size) < page.total

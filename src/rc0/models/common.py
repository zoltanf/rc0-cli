"""Shared model primitives."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Rc0Model(BaseModel):
    """Base class — permissive on extras so the API can evolve without breaking."""

    model_config = ConfigDict(extra="allow", frozen=True, str_strip_whitespace=True)

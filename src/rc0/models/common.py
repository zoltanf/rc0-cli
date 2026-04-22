"""Shared model primitives."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Rc0Model(BaseModel):
    """Base class for API *response* models.

    Permissive on extras so the API can evolve without breaking us.
    """

    model_config = ConfigDict(extra="allow", frozen=True, str_strip_whitespace=True)


class Rc0WriteModel(BaseModel):
    """Base class for API *request* body models.

    Strict on extras — unknown fields at construction time are an error, so
    typos and drift-with-the-spec surface loudly instead of being serialised
    into the outgoing request.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

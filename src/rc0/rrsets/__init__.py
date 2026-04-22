"""Phase-3 RRset input pipeline.

``parse.py`` turns each of the three input formats specified in mission-plan
§12 — flags, JSON/YAML files, and BIND zone files — into Pydantic rrset models
ready for :mod:`rc0.api.rrsets_write`.

Validation (client-side RRset rules) lives in :mod:`rc0.validation.rrsets`.
This package only produces models; callers must run the validators before
dispatching the request.
"""

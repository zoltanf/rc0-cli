"""Client-side validation (§12).

Phase 3 populated :mod:`rc0.validation.rrsets` with the rrset validators. Keep
new phase-specific validators in their own submodules; ``__init__`` stays
intentionally empty so imports like ``from rc0.validation.rrsets import …``
work without pulling in unrelated code.
"""

"""Opponent profile store for the Counterfactual Lab.

Per AgDR-0002 (`docs/agdr/AgDR-0002-opponent-data-source.md`):

* v1 reads StatsBomb Open Data, gated to non-production environments by
  :func:`athletiq.data.opponents.license_gate.assert_license_tier_allows`.
* v2 will swap in a paid feed via a new ``OpponentEventStore``
  implementation. The interface and consumers stay unchanged.

Public surface
--------------

* :class:`OpponentEventStore` — Protocol every store implementation satisfies.
* :class:`OpponentProfile` — domain type returned by ``get_profile``.
* :class:`HistogramSamples` — compact 1-D distribution.
* :class:`StatsBombOpenStore` — v1 implementation (CC BY-NC-SA 4.0).
* :func:`assert_license_tier_allows` — fail-closed env-var gate.
"""

from athletiq.data.opponents.license_gate import (
    LicenseTierError,
    assert_license_tier_allows,
)
from athletiq.data.opponents.store import (
    HistogramSamples,
    OpponentEventStore,
    OpponentProfile,
)

__all__ = [
    "HistogramSamples",
    "LicenseTierError",
    "OpponentEventStore",
    "OpponentProfile",
    "assert_license_tier_allows",
]

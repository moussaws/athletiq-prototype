"""Fail-closed license gate for opponent-data reads.

Per AgDR-0002: the v1 StatsBomb Open Data path is licensed CC BY-NC-SA 4.0
(non-commercial). It is allowed only in development, demo, and internal
environments. Any production environment must use a paid feed.

The gate is fail-closed by design: if either ``ATHLETIQ_LICENSE_TIER`` or
``ATHLETIQ_ENV`` is unset, the gate raises. Forgetting to configure the
runtime is treated as the most serious failure mode, not the most lenient.

Allowed env combinations
------------------------

================  ============  ==================
LICENSE_TIER      ENV           Decision
================  ============  ==================
``open``          ``dev``       allowed
``open``          ``demo``      allowed
``open``          ``internal``  allowed
``open``          ``prod``      **VIOLATION**
``open``          ``staging``   **VIOLATION**
``paid``          *(any)*       allowed
*(unset)*         *(any)*       **VIOLATION** (fail-closed)
*(any)*           *(unset)*     **VIOLATION** (fail-closed)
================  ============  ==================
"""

from __future__ import annotations

import os

_PERMISSIVE_ENVS: frozenset[str] = frozenset({"dev", "demo", "internal"})
_VALID_TIERS: frozenset[str] = frozenset({"open", "paid"})


class LicenseTierError(RuntimeError):
    """Raised when an opponent-data read is attempted under a license
    tier that the current environment doesn't permit. Caught at the
    HTTP boundary and surfaced as ``HTTP 403 LICENSE_TIER_VIOLATION``.
    """


def assert_license_tier_allows(*, store_tier: str) -> None:
    """Block the call unless ``store_tier`` is allowed in the current env.

    ``store_tier`` is the license tier of the STORE doing the read
    (``"open"`` for ``StatsBombOpenStore``, ``"paid"`` for a future
    StatsBomb-Pro / Wyscout / Opta store). The environment is read from
    ``ATHLETIQ_LICENSE_TIER`` and ``ATHLETIQ_ENV``.

    Raises
    ------
    LicenseTierError
        If either env var is unset, or if the combination is disallowed
        per the table in the module docstring.
    """
    if store_tier not in _VALID_TIERS:
        raise LicenseTierError(
            f"store_tier must be one of {sorted(_VALID_TIERS)}, got {store_tier!r}"
        )

    env_tier = os.environ.get("ATHLETIQ_LICENSE_TIER")
    env = os.environ.get("ATHLETIQ_ENV")

    if env_tier is None or env is None:
        raise LicenseTierError(
            "ATHLETIQ_LICENSE_TIER and ATHLETIQ_ENV must both be set; "
            "fail-closed gate refuses to assume a default. "
            f"Got LICENSE_TIER={env_tier!r}, ENV={env!r}."
        )

    if env_tier not in _VALID_TIERS:
        raise LicenseTierError(
            f"ATHLETIQ_LICENSE_TIER must be one of {sorted(_VALID_TIERS)}, got {env_tier!r}."
        )

    if store_tier == "paid":
        # Paid stores work everywhere — they have explicit contractual
        # data-handling terms and don't carry the NC restriction.
        return

    # store_tier == "open" — allowed only in permissive envs and only
    # when the runtime tier matches the store tier (no surprise downgrade).
    if env_tier != "open":
        raise LicenseTierError(
            f"open-data store may not be used under ATHLETIQ_LICENSE_TIER="
            f"{env_tier!r}; switch to a paid store or set tier=open in a "
            f"non-production environment."
        )
    if env not in _PERMISSIVE_ENVS:
        raise LicenseTierError(
            f"open-data store is forbidden in ATHLETIQ_ENV={env!r}; "
            f"allowed envs: {sorted(_PERMISSIVE_ENVS)}."
        )

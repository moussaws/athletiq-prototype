"""Tests for the opponent profile store + license gate.

The headline test (and the reason this module is in the spike scope) is
``test_license_gate_fails_closed_when_env_unset`` — it asserts the
mechanical guarantee that opponent-data reads cannot succeed when the
operator has forgotten to declare the runtime tier. That's the
fail-closed contract spelled out in AgDR-0002.
"""

from __future__ import annotations

import pytest

from athletiq.data.opponents import (
    HistogramSamples,
    LicenseTierError,
    OpponentProfile,
    assert_license_tier_allows,
)

# ─── License gate ───────────────────────────────────────────────────────


def test_license_gate_fails_closed_when_env_unset(monkeypatch):
    """The contract: forgetting to set ATHLETIQ_LICENSE_TIER + ATHLETIQ_ENV
    must NOT silently default to a permissive state. The gate raises."""
    monkeypatch.delenv("ATHLETIQ_LICENSE_TIER", raising=False)
    monkeypatch.delenv("ATHLETIQ_ENV", raising=False)
    with pytest.raises(LicenseTierError, match="must both be set"):
        assert_license_tier_allows(store_tier="open")
    with pytest.raises(LicenseTierError, match="must both be set"):
        assert_license_tier_allows(store_tier="paid")


def test_license_gate_fails_closed_when_only_one_var_set(monkeypatch):
    monkeypatch.setenv("ATHLETIQ_LICENSE_TIER", "open")
    monkeypatch.delenv("ATHLETIQ_ENV", raising=False)
    with pytest.raises(LicenseTierError, match="must both be set"):
        assert_license_tier_allows(store_tier="open")

    monkeypatch.delenv("ATHLETIQ_LICENSE_TIER", raising=False)
    monkeypatch.setenv("ATHLETIQ_ENV", "dev")
    with pytest.raises(LicenseTierError, match="must both be set"):
        assert_license_tier_allows(store_tier="open")


@pytest.mark.parametrize("env", ["dev", "demo", "internal"])
def test_open_store_allowed_in_permissive_envs(monkeypatch, env):
    monkeypatch.setenv("ATHLETIQ_LICENSE_TIER", "open")
    monkeypatch.setenv("ATHLETIQ_ENV", env)
    # Should not raise.
    assert_license_tier_allows(store_tier="open")


@pytest.mark.parametrize("env", ["prod", "production", "staging"])
def test_open_store_blocked_in_production_envs(monkeypatch, env):
    monkeypatch.setenv("ATHLETIQ_LICENSE_TIER", "open")
    monkeypatch.setenv("ATHLETIQ_ENV", env)
    with pytest.raises(LicenseTierError, match="forbidden"):
        assert_license_tier_allows(store_tier="open")


@pytest.mark.parametrize("env", ["dev", "demo", "internal", "prod", "staging"])
def test_paid_store_allowed_everywhere(monkeypatch, env):
    """Paid stores have explicit data-handling contracts and don't carry
    the NC restriction — gate lets them through in any env."""
    monkeypatch.setenv("ATHLETIQ_LICENSE_TIER", "paid")
    monkeypatch.setenv("ATHLETIQ_ENV", env)
    assert_license_tier_allows(store_tier="paid")


def test_open_store_blocked_when_runtime_tier_is_paid(monkeypatch):
    """Once the runtime declares paid, no open-data reads slip through —
    even in dev — because that would mean code paths in dev would surprise
    you when promoted to prod."""
    monkeypatch.setenv("ATHLETIQ_LICENSE_TIER", "paid")
    monkeypatch.setenv("ATHLETIQ_ENV", "dev")
    with pytest.raises(LicenseTierError, match="may not be used"):
        assert_license_tier_allows(store_tier="open")


def test_invalid_store_tier_rejected(monkeypatch):
    monkeypatch.setenv("ATHLETIQ_LICENSE_TIER", "open")
    monkeypatch.setenv("ATHLETIQ_ENV", "dev")
    with pytest.raises(LicenseTierError, match="store_tier must be"):
        assert_license_tier_allows(store_tier="bogus")


# ─── OpponentProfile round-trip ─────────────────────────────────────────


def test_opponent_profile_roundtrip():
    """Serialise → JSON shape → deserialise yields an equal profile."""
    profile = OpponentProfile(
        opponent_id="test-team-2025-26",
        display_name="Test Team — Test League 2025/26",
        source_attribution="Test fixture",
        competition="Test League",
        season="2025/2026",
        matches_observed=3,
        formation_mix=[("4-3-3", 0.66), ("4-2-3-1", 0.34)],
        def_line_height_distribution=HistogramSamples(
            bin_edges=[0.0, 35.0, 70.0, 105.0],
            counts=[0, 2, 1],
        ),
        pressing_intensity_per_zone=[[0.05] * 3 for _ in range(4)],  # sums to 0.6
        positional_heatmap=[[0.0] * 52 for _ in range(34)],
        transition_speed_proxy=4.2,
        notes=["test fixture"],
    )
    d = profile.to_dict()
    restored = OpponentProfile.from_dict(d)
    assert restored == profile

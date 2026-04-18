"""Verify pitch control surface properties (Eq. 7)."""

from __future__ import annotations

import pytest

from athletiq.data.synthetic import generate_synthetic_snapshot
from athletiq.metrics.pitch_control import PlayerSnapshot, pitch_control_surface


def test_shape_matches_request() -> None:
    players = generate_synthetic_snapshot(seed=0)
    phi, xx, yy = pitch_control_surface(players, grid_shape=(34, 52))
    assert phi.shape == (34, 52)
    assert xx.shape == phi.shape
    assert yy.shape == phi.shape


def test_surface_bounded_in_unit_interval() -> None:
    players = generate_synthetic_snapshot(seed=1)
    phi, _, _ = pitch_control_surface(players, grid_shape=(20, 30))
    assert phi.min() >= 0.0 and phi.max() <= 1.0


def test_attacker_dominates_local_region() -> None:
    # lone attacker at (50,34), lone defender at (95,34) — attacker should
    # own most of the left half of the pitch.
    players = [
        PlayerSnapshot(x=50, y=34, team=0),
        PlayerSnapshot(x=95, y=34, team=1),
    ]
    phi, _, _ = pitch_control_surface(players, grid_shape=(10, 20))
    assert phi[:, :5].mean() > 0.9
    assert phi[:, -5:].mean() < 0.1


def test_errors_without_both_teams() -> None:
    players = [PlayerSnapshot(x=50, y=34, team=0)]
    with pytest.raises(ValueError):
        pitch_control_surface(players, grid_shape=(10, 20))

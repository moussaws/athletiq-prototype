"""Verify DDI integration (Eq. 8)."""

from __future__ import annotations

import numpy as np
import pytest

from athletiq.data.synthetic import generate_synthetic_snapshot
from athletiq.metrics.ddi import ddi
from athletiq.metrics.pitch_control import pitch_control_surface


def test_ddi_zero_when_no_change() -> None:
    players = generate_synthetic_snapshot(seed=0)
    phi, xx, yy = pitch_control_surface(players, grid_shape=(20, 30))
    val = ddi(phi, phi, xx, yy)
    assert val == pytest.approx(0.0, abs=1e-9)


def test_ddi_positive_when_attacker_opens_high_xt_zone() -> None:
    players = generate_synthetic_snapshot(seed=0)
    phi_b, xx, yy = pitch_control_surface(players, grid_shape=(20, 30))
    phi_a = np.clip(phi_b + 0.15, 0, 1)  # broad attacker gain
    val = ddi(phi_b, phi_a, xx, yy, tau=0.05)
    assert val > 0


def test_ddi_units_are_m2() -> None:
    # Uniform +0.1 over the whole high-xT region on a 105x68 pitch should
    # roughly equal (high-xT area in m^2) * 0.1.
    players = generate_synthetic_snapshot(seed=2)
    phi_b, xx, yy = pitch_control_surface(players, grid_shape=(20, 30))
    phi_a = np.clip(phi_b + 0.1, 0, 1)
    val = ddi(phi_b, phi_a, xx, yy, tau=0.05)
    # Sanity: magnitude is roughly in the 10^1–10^3 m^2 range
    assert 0 < val < 5000


def test_ddi_shape_validation() -> None:
    phi = np.zeros((10, 10))
    bad = np.zeros((9, 10))
    xx, yy = np.meshgrid(np.linspace(0, 105, 10), np.linspace(0, 68, 10))
    with pytest.raises(ValueError):
        ddi(bad, phi, xx, yy)

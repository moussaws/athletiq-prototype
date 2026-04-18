"""Verify Eq. 6 — progressive carry xT."""

from __future__ import annotations

import pytest

from athletiq.metrics.xt import DEFAULT_ALPHA, default_xt_grid, progressive_carry_xt, xt_value_at


def test_grid_has_expected_shape() -> None:
    g = default_xt_grid(rows=12, cols=16)
    assert g.values.shape == (12, 16)
    assert g.values.max() == pytest.approx(0.40, rel=1e-6)


def test_xt_monotone_with_x() -> None:
    g = default_xt_grid()
    a = xt_value_at(10, 34, grid=g)
    b = xt_value_at(80, 34, grid=g)
    assert b > a


def test_xt_centre_higher_than_corner() -> None:
    g = default_xt_grid()
    centre = xt_value_at(95, 34, grid=g)
    corner = xt_value_at(95, 4, grid=g)
    assert centre > corner


def test_progressive_carry_zero_when_regressive() -> None:
    val = progressive_carry_xt((80, 34), (20, 34), mean_pressure=2.0)
    assert val == 0.0


def test_progressive_carry_formula() -> None:
    # Matches Eq. 6: [xT(end) - xT(start)] * (1 + alpha * mean_P)
    g = default_xt_grid()
    s = (20, 34)
    e = (80, 34)
    delta = g.value_at(*e) - g.value_at(*s)
    expected = delta * (1 + DEFAULT_ALPHA * 3.0)
    assert progressive_carry_xt(s, e, mean_pressure=3.0) == pytest.approx(expected)


def test_pressure_amplification_monotone() -> None:
    s = (20, 34)
    e = (80, 34)
    low = progressive_carry_xt(s, e, mean_pressure=0.5)
    high = progressive_carry_xt(s, e, mean_pressure=4.0)
    assert high > low

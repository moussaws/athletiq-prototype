"""Verify Eq. 1–4 from the AthletIQ paper."""

from __future__ import annotations

import math

import pytest

from athletiq.metrics.pressure import (
    DEFAULT_INFLUENCE_RADIUS_M,
    collective_pressure,
    individual_unit_pressure,
    mean_collective_pressure,
    raw_individual_pressure,
)


def test_raw_pressure_zero_when_outside_radius() -> None:
    # defender 6m away, radius 5m -> 0
    out = raw_individual_pressure([[0, 0]], [6, 0], radius=5.0)
    assert out.shape == (1,)
    assert out[0] == 0.0


def test_raw_pressure_quadratic_decay_matches_eq1() -> None:
    # At d=0, pressure = r^2. At d=r/2, pressure = (r/2)^2.
    r = 5.0
    for d in [0.0, 1.0, 2.5, 4.9]:
        out = raw_individual_pressure([[d, 0]], [0, 0], radius=r)
        expected = (r - d) ** 2
        assert out[0] == pytest.approx(expected, abs=1e-9)


def test_unit_pressure_normalizes_by_area() -> None:
    r = 5.0
    raw = raw_individual_pressure([[1, 0]], [0, 0], radius=r)
    unit = individual_unit_pressure([[1, 0]], [0, 0], radius=r)
    assert unit[0] == pytest.approx(raw[0] / (math.pi * r**2), rel=1e-9)


def test_collective_sums_over_defenders() -> None:
    r = 5.0
    defenders = [[1, 0], [2, 0], [10, 0]]  # third one outside radius
    carrier = [0, 0]
    unit = individual_unit_pressure(defenders, carrier, radius=r)
    assert unit[2] == 0.0
    assert collective_pressure(defenders, carrier, radius=r) == pytest.approx(unit.sum(), rel=1e-12)


def test_default_radius_constant() -> None:
    assert DEFAULT_INFLUENCE_RADIUS_M == 5.0


def test_mean_collective_pressure_over_frames() -> None:
    defenders_per_frame = [[[1, 0]], [[2, 0]], [[3, 0]]]
    carriers = [[0, 0], [0, 0], [0, 0]]
    mean_p = mean_collective_pressure(defenders_per_frame, carriers, radius=5.0)
    # P values at d=1,2,3 are 16/(pi*25), 9/(pi*25), 4/(pi*25)
    expected = (16 + 9 + 4) / (math.pi * 25) / 3
    assert mean_p == pytest.approx(expected, rel=1e-9)


def test_mean_pressure_empty_is_zero() -> None:
    assert mean_collective_pressure([], []) == 0.0


def test_length_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        mean_collective_pressure([[[1, 0]]], [[0, 0], [1, 1]])


def test_radius_must_be_positive() -> None:
    with pytest.raises(ValueError):
        raw_individual_pressure([[0, 0]], [0, 0], radius=0.0)


def test_shape_validation() -> None:
    with pytest.raises(ValueError):
        raw_individual_pressure([[0, 0, 0]], [0, 0])

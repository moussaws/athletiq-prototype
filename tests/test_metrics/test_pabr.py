"""Verify Eq. 5 — PABR."""

from __future__ import annotations

import math

import pytest

from athletiq.metrics.retention import PossessionSequence, pabr


def test_pabr_empty_returns_zero() -> None:
    assert pabr([]) == 0.0


def test_pabr_all_retained_equals_one() -> None:
    seqs = [
        PossessionSequence(mean_pressure=0.1, retained=True),
        PossessionSequence(mean_pressure=3.0, retained=True),
    ]
    assert pabr(seqs) == pytest.approx(1.0)


def test_pabr_none_retained_equals_zero() -> None:
    seqs = [
        PossessionSequence(mean_pressure=0.1, retained=False),
        PossessionSequence(mean_pressure=3.0, retained=False),
    ]
    assert pabr(seqs) == pytest.approx(0.0)


def test_pabr_exponential_weighting_matches_formula() -> None:
    # One low-pressure retained, one high-pressure lost.
    # PABR = exp(0.1) / (exp(0.1) + exp(3.0))  ~= very small
    seqs = [
        PossessionSequence(mean_pressure=0.1, retained=True),
        PossessionSequence(mean_pressure=3.0, retained=False),
    ]
    expected = math.exp(0.1) / (math.exp(0.1) + math.exp(3.0))
    assert pabr(seqs) == pytest.approx(expected, rel=1e-9)


def test_pabr_high_pressure_retained_dominates() -> None:
    # High-pressure retained contributes orders of magnitude more to numerator.
    seqs = [
        PossessionSequence(mean_pressure=0.1, retained=False),
        PossessionSequence(mean_pressure=5.0, retained=True),
    ]
    # With exponential weighting, the high-pressure success swamps the numerator
    assert pabr(seqs) > 0.99


def test_pabr_stable_under_large_pressure() -> None:
    # Values up to mean_pressure = 50 must not overflow exp
    seqs = [PossessionSequence(mean_pressure=50.0, retained=True)]
    assert pabr(seqs) == pytest.approx(1.0)

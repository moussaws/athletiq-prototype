"""Paper §4.4.2 — WASPAS fitness score (Eq. 13)."""

from __future__ import annotations

import numpy as np
import pytest

from athletiq.scouting.waspas import normalize_benefit, waspas_scores


def test_waspas_scores_shape() -> None:
    Y = np.array([[1.0, 0.5], [0.5, 1.0]])
    Yn = normalize_benefit(Y)
    w = np.array([0.6, 0.4])
    q = waspas_scores(Yn, w)
    assert q.shape == (2,)


def test_waspas_maxes_at_uniform_perfect_row() -> None:
    Y = np.array([[1.0, 1.0, 1.0], [0.5, 0.5, 0.5]])
    w = np.array([0.2, 0.3, 0.5])
    q = waspas_scores(Y, w)
    assert q[0] == pytest.approx(1.0)
    assert q[1] < 1.0


def test_waspas_punishes_categorical_weakness() -> None:
    """A row with a single near-zero category must be penalized by the multiplicative term."""
    balanced = np.array([0.5, 0.5, 0.5])
    weak = np.array([0.99, 0.99, 0.01])
    Y = np.vstack([balanced, weak])
    w = np.array([1 / 3, 1 / 3, 1 / 3])
    q = waspas_scores(Y, w)
    assert q[0] > q[1]


def test_weights_must_sum_to_one() -> None:
    Y = np.array([[0.5, 0.5]])
    with pytest.raises(ValueError):
        waspas_scores(Y, np.array([0.3, 0.3]))


def test_normalize_benefit_ratio() -> None:
    Y = np.array([[1.0, 2.0], [3.0, 4.0]])
    Yn = normalize_benefit(Y)
    assert Yn.max(axis=0)[0] == 1.0
    assert Yn.max(axis=0)[1] == 1.0

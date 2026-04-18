"""Paper §4.4.1 — AHP weights + CR (Eq. 12)."""

from __future__ import annotations

import numpy as np
import pytest

from athletiq.scouting.ahp import ahp_weights, consistency_ratio, validate_consistency


def _reciprocal(values: list[list[float]]) -> np.ndarray:
    return np.array(values, dtype=np.float64)


def test_perfectly_consistent_matrix_cr_is_zero() -> None:
    # A_{ij} = w_i / w_j is exactly consistent => CR = 0
    w_true = np.array([0.5, 0.3, 0.2])
    A = np.outer(w_true, 1.0 / w_true)
    assert consistency_ratio(A) == pytest.approx(0.0, abs=1e-9)
    w = ahp_weights(A)
    assert np.allclose(w, w_true, atol=1e-6)


def test_saaty_canonical_3x3_is_consistent() -> None:
    # Classic Saaty textbook example
    A = _reciprocal(
        [
            [1, 5, 3],
            [1 / 5, 1, 1 / 3],
            [1 / 3, 3, 1],
        ]
    )
    cr = consistency_ratio(A)
    assert cr < 0.10


def test_inconsistent_matrix_detected() -> None:
    A = _reciprocal(
        [
            [1, 9, 1 / 9],
            [1 / 9, 1, 9],
            [9, 1 / 9, 1],
        ]
    )
    cr = consistency_ratio(A)
    assert cr > 0.10
    with pytest.raises(ValueError):
        validate_consistency(A)


def test_non_positive_entries_rejected() -> None:
    A = np.array([[1, 0], [1, 1]], dtype=np.float64)
    with pytest.raises(ValueError):
        ahp_weights(A)


def test_non_reciprocal_rejected() -> None:
    A = np.array([[1, 2], [3, 1]], dtype=np.float64)
    with pytest.raises(ValueError):
        ahp_weights(A)


def test_weights_sum_to_one() -> None:
    A = _reciprocal(
        [
            [1, 2, 3, 4],
            [1 / 2, 1, 2, 3],
            [1 / 3, 1 / 2, 1, 2],
            [1 / 4, 1 / 3, 1 / 2, 1],
        ]
    )
    w = ahp_weights(A)
    assert w.sum() == pytest.approx(1.0, rel=1e-12)
    assert (w > 0).all()

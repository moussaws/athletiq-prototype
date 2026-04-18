"""Paper §4.1 — vectorization, z-score, position-wise imputation."""

from __future__ import annotations

import numpy as np
import pytest

from athletiq.data.synthetic import generate_synthetic_cohort
from athletiq.scouting.vectorize import PlayerVector, build_feature_matrix


def test_z_score_has_zero_mean() -> None:
    players = generate_synthetic_cohort(n=50, seed=1)
    _, X = build_feature_matrix(players)
    assert np.allclose(X.mean(axis=0), 0.0, atol=1e-9)


def test_z_score_has_unit_std() -> None:
    players = generate_synthetic_cohort(n=50, seed=1)
    _, X = build_feature_matrix(players)
    # population std (ddof=0) — the implementation uses ddof=0 to be robust
    assert np.allclose(X.std(axis=0, ddof=0), 1.0, atol=1e-9)


def test_position_specific_imputation() -> None:
    """A missing value on a CB should be filled with the CB-only mean, not the global mean."""
    players = [
        PlayerVector("P1", "A", "CB", "X", 25, 10, False, {"speed": 10.0}),
        PlayerVector("P2", "CB2", "CB", "X", 25, 10, False, {"speed": 12.0}),
        PlayerVector("P3", "CB3", "CB", "X", 25, 10, False, {"speed": float("nan")}),
        # many strikers with much higher speed values
        *[
            PlayerVector(f"S{i}", f"S{i}", "ST", "X", 25, 10, False, {"speed": 30.0})
            for i in range(5)
        ],
    ]
    _, X = build_feature_matrix(players)
    # Before z-score the CB imputed value must be 11 (CB mean), not the global mean.
    # After z-score we can't read that directly, but we can check that the
    # z-score of P3 is close to the z-score of the CB average (= (11 - global_mean)/sigma).
    zs = X[:, 0]
    cb_z = zs[:3]  # three CBs, one imputed
    assert cb_z[2] == pytest.approx((cb_z[0] + cb_z[1]) / 2, rel=1e-6)


def test_reindex_to_requested_feature_names() -> None:
    players = generate_synthetic_cohort(n=10, seed=0)
    names = ["pabr", "xt_carry"]
    _, X = build_feature_matrix(players, feature_names=names)
    assert X.shape[1] == 2

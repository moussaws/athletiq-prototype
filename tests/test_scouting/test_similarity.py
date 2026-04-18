"""Paper §4.3 — hybrid KNN retrieval."""

from __future__ import annotations

import numpy as np
import pytest

from athletiq.scouting.similarity import hybrid_distance, knn_similar_players


def test_hybrid_bounds() -> None:
    q = np.array([1.0, 0.0, 0.0])
    cands = np.array(
        [
            [1.0, 0.0, 0.0],  # identical
            [10.0, 0.0, 0.0],  # same direction, far
            [-1.0, 0.0, 0.0],  # opposite direction
        ]
    )
    hyb, euc, cos = hybrid_distance(q, cands, lam=0.5)
    # Identical candidate has both zero Euclidean and cosine=1 -> hybrid == 0
    assert hyb[0] == pytest.approx(0.0, abs=1e-12)
    assert cos[2] == pytest.approx(-1.0)
    assert hyb[2] > hyb[1]  # opposite direction worse than same-direction-far


def test_knn_returns_k_results_excluding_self() -> None:
    rng = np.random.default_rng(0)
    X = rng.normal(size=(20, 5))
    ids = [f"P{i}" for i in range(20)]
    res = knn_similar_players(X[3], X, ids, k=5, lam=0.5, exclude_ids={"P3"})
    assert len(res) == 5
    assert all(r.player_id != "P3" for r in res)


def test_lam_extremes_match_pure_metrics() -> None:
    rng = np.random.default_rng(1)
    X = rng.normal(size=(30, 6))
    q = X[0]
    hyb_euc_only, _, _ = hybrid_distance(q, X, lam=1.0)
    hyb_cos_only, _, _ = hybrid_distance(q, X, lam=0.0)
    # lam=1 -> hybrid is just normalized Euclidean, lam=0 -> just cosine distance
    assert np.argmin(hyb_euc_only) == 0
    assert np.argmin(hyb_cos_only) == 0


def test_rejects_bad_inputs() -> None:
    q = np.array([1.0, 0.0])
    with pytest.raises(ValueError):
        hybrid_distance(q, np.zeros((3, 3)))
    with pytest.raises(ValueError):
        hybrid_distance(q, np.zeros((3, 2)), lam=2.0)
    with pytest.raises(ValueError):
        knn_similar_players(q, np.zeros((3, 2)), ["a", "b", "c"], k=0)

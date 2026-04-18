"""Paper §4.2 — PCA + silhouette-optimal K-Means."""

from __future__ import annotations

import numpy as np

from athletiq.data.synthetic import generate_synthetic_cohort
from athletiq.scouting.cluster import (
    fit_kmeans_silhouette,
    fit_pca,
    tactical_archetypes,
)
from athletiq.scouting.vectorize import build_feature_matrix


def test_pca_retains_at_least_variance_target() -> None:
    players = generate_synthetic_cohort(n=80, seed=0)
    _, X = build_feature_matrix(players)
    pca = fit_pca(X, variance_target=0.90)
    assert pca.explained_variance >= 0.90


def test_pca_reduces_dimensions() -> None:
    players = generate_synthetic_cohort(n=80, seed=0)
    _, X = build_feature_matrix(players)
    pca = fit_pca(X, variance_target=0.80)
    assert pca.X_reduced.shape[0] == X.shape[0]
    assert pca.X_reduced.shape[1] <= X.shape[1]


def test_kmeans_silhouette_picks_reasonable_k() -> None:
    # Three well-separated gaussian blobs -> silhouette should prefer k=3
    rng = np.random.default_rng(0)
    X = np.vstack(
        [
            rng.normal(loc=[0, 0], scale=0.3, size=(30, 2)),
            rng.normal(loc=[5, 0], scale=0.3, size=(30, 2)),
            rng.normal(loc=[0, 5], scale=0.3, size=(30, 2)),
        ]
    )
    result = fit_kmeans_silhouette(X, k_range=range(2, 6))
    assert result.k == 3
    assert result.silhouette > 0.5


def test_tactical_archetypes_per_position() -> None:
    players = generate_synthetic_cohort(n=160, seed=1)
    positions = np.array([p.position for p in players])
    _, X = build_feature_matrix(players)
    out = tactical_archetypes(X, positions)
    # We should have clusters for most positions
    assert len(out) >= 5
    for _, (_, cl) in out.items():
        assert cl.k >= 2

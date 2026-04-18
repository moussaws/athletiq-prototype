"""Dimensionality reduction + tactical clustering (paper §4.2).

PCA retaining >= 90% of variance, fit independently per positional subgroup.
K-Means with silhouette-maximal k (Eq. 10).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score

FloatArray = npt.NDArray[np.floating]


@dataclass(frozen=True, slots=True)
class PCAResult:
    model: PCA
    X_reduced: FloatArray
    explained_variance: float


def fit_pca(X: FloatArray, variance_target: float = 0.90) -> PCAResult:
    """Fit PCA retaining >= ``variance_target`` of the variance."""
    if not 0.0 < variance_target <= 1.0:
        raise ValueError("variance_target must be in (0, 1]")
    pca = PCA(n_components=variance_target, svd_solver="full")
    X_red = pca.fit_transform(X)
    return PCAResult(
        model=pca,
        X_reduced=X_red.astype(np.float64),
        explained_variance=float(pca.explained_variance_ratio_.sum()),
    )


@dataclass(frozen=True, slots=True)
class ClusteringResult:
    labels: np.ndarray
    k: int
    silhouette: float
    centers: FloatArray


def fit_kmeans_silhouette(
    X: FloatArray,
    k_range: range | None = None,
    random_state: int = 42,
) -> ClusteringResult:
    """Eq. 10 — pick the k in ``k_range`` maximizing silhouette score."""
    if X.shape[0] < 3:
        raise ValueError("need at least 3 samples to cluster")
    k_range = k_range or range(2, min(9, X.shape[0]))

    best: ClusteringResult | None = None
    for k in k_range:
        if k >= X.shape[0]:
            continue
        km = KMeans(n_clusters=k, n_init=10, random_state=random_state)
        labels = km.fit_predict(X)
        if len(np.unique(labels)) < 2:
            continue
        score = float(silhouette_score(X, labels))
        if best is None or score > best.silhouette:
            best = ClusteringResult(
                labels=labels,
                k=int(k),
                silhouette=score,
                centers=km.cluster_centers_.astype(np.float64),
            )
    if best is None:
        raise RuntimeError("no valid k produced >= 2 clusters")
    return best


def tactical_archetypes(
    X: FloatArray,
    positions: np.ndarray,
    variance_target: float = 0.90,
    k_range: range | None = None,
) -> dict[str, tuple[PCAResult, ClusteringResult]]:
    """Run PCA+K-Means independently per positional subgroup.

    Returns ``{position: (pca_result, clustering_result)}``.
    """
    out: dict[str, tuple[PCAResult, ClusteringResult]] = {}
    for pos in np.unique(positions):
        mask = positions == pos
        if mask.sum() < 3:
            continue
        pca = fit_pca(X[mask], variance_target=variance_target)
        clust = fit_kmeans_silhouette(pca.X_reduced, k_range=k_range)
        out[str(pos)] = (pca, clust)
    return out

"""Pillar B — AI-driven technical scouting pipeline.

Implements Section 4 of the AthletIQ paper:

* Player vectorization + z-score normalization + position-aware imputation
* Dimensionality reduction via PCA, retaining >= 90% variance
* K-Means clustering with silhouette-optimal ``k``           (Eq. 10)
* Hybrid KNN similarity retrieval (Euclidean + cosine)       (Eq. 11)
* AHP positional weighting + Consistency Ratio check         (Eq. 12)
* WASPAS positional fitness score                            (Eq. 13)
* Binary Integer Programming roster optimization             (Eq. 14–18)
"""

from athletiq.scouting.ahp import ahp_weights, consistency_ratio
from athletiq.scouting.bip import SquadOptimizationResult, optimize_squad
from athletiq.scouting.cluster import (
    fit_kmeans_silhouette,
    fit_pca,
    tactical_archetypes,
)
from athletiq.scouting.similarity import hybrid_distance, knn_similar_players
from athletiq.scouting.vectorize import PlayerVector, build_feature_matrix
from athletiq.scouting.waspas import waspas_scores

__all__ = [
    "PlayerVector",
    "SquadOptimizationResult",
    "ahp_weights",
    "build_feature_matrix",
    "consistency_ratio",
    "fit_kmeans_silhouette",
    "fit_pca",
    "hybrid_distance",
    "knn_similar_players",
    "optimize_squad",
    "tactical_archetypes",
    "waspas_scores",
]

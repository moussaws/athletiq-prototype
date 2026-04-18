"""Process-global in-memory state for the prototype API.

For v1 we keep everything in-memory: the synthetic cohort is generated on
startup and served from RAM. Swapping this for PostgreSQL/TimescaleDB is a
drop-in replacement behind the ``CohortStore`` interface below.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from threading import Lock

import numpy as np

from athletiq.data.synthetic import generate_synthetic_cohort
from athletiq.scouting.cluster import ClusteringResult, PCAResult, fit_pca
from athletiq.scouting.vectorize import PlayerVector, build_feature_matrix


@dataclass
class CohortStore:
    players: list[PlayerVector]
    meta_df: object  # pandas DataFrame — typed as object to avoid pandas in stubs
    X: np.ndarray
    pca: PCAResult
    clusters_by_position: dict[str, tuple[PCAResult, ClusteringResult]]


_LOCK = Lock()
_STORE: CohortStore | None = None


@lru_cache(maxsize=1)
def _default_feature_names() -> list[str]:
    return [
        "passes_completed",
        "take_ons",
        "shots",
        "tackles",
        "interceptions",
        "aerial_duels_won",
        "sprint_count",
        "accel_count",
        "pabr",
        "xt_carry",
        "ddi",
    ]


def bootstrap(n: int = 240, seed: int = 42) -> CohortStore:
    """Build the in-memory cohort + cached PCA on startup / first request."""
    global _STORE
    with _LOCK:
        if _STORE is not None:
            return _STORE
        players = generate_synthetic_cohort(n=n, seed=seed)
        meta, X = build_feature_matrix(players, feature_names=_default_feature_names())
        pca = fit_pca(X, variance_target=0.95)
        # lazy: per-position clusters are built on demand by the scouting route
        _STORE = CohortStore(
            players=players,
            meta_df=meta,
            X=X,
            pca=pca,
            clusters_by_position={},
        )
        return _STORE


def get_store() -> CohortStore:
    return _STORE if _STORE is not None else bootstrap()


def reset_store() -> None:
    global _STORE
    with _LOCK:
        _STORE = None

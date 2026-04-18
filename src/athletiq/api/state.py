"""Process-global in-memory state for the prototype API.

On startup we load the committed FBRef Big-5 2023-24 cohort (≈816 real
players across the five top European leagues, CC0-licensed source). The
synthetic generator is kept as an explicit fallback for environments
where the CSV is missing and as a test fixture for unit tests.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from threading import Lock

import numpy as np

from athletiq.data.fbref import load_fbref_cohort
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
    provenance: dict[str, object] = field(default_factory=dict)


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


def _load_players() -> tuple[list[PlayerVector], dict[str, object]]:
    """Load the real FBRef cohort; fall back to synthetic if missing/disabled."""
    forced = os.environ.get("ATHLETIQ_COHORT_SOURCE", "").lower()
    if forced == "synthetic":
        players = generate_synthetic_cohort(n=240, seed=42)
        return players, {"source": "synthetic", "n_players": len(players), "seed": 42}
    try:
        cohort = load_fbref_cohort()
        return cohort.as_list, dict(cohort.provenance)
    except FileNotFoundError:
        players = generate_synthetic_cohort(n=240, seed=42)
        return players, {
            "source": "synthetic (FBRef CSV missing)",
            "n_players": len(players),
            "seed": 42,
        }


def bootstrap() -> CohortStore:
    """Build the in-memory cohort + cached PCA on startup / first request."""
    global _STORE
    with _LOCK:
        if _STORE is not None:
            return _STORE
        players, provenance = _load_players()
        meta, X = build_feature_matrix(players, feature_names=_default_feature_names())
        pca = fit_pca(X, variance_target=0.95)
        _STORE = CohortStore(
            players=players,
            meta_df=meta,
            X=X,
            pca=pca,
            clusters_by_position={},
            provenance=provenance,
        )
        return _STORE


def get_store() -> CohortStore:
    return _STORE if _STORE is not None else bootstrap()


def reset_store() -> None:
    global _STORE
    with _LOCK:
        _STORE = None

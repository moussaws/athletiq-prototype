"""Hybrid similarity retrieval (paper §4.3, Eq. 11).

    d_lambda(i, j) = lambda * d_Euc(i, j) + (1 - lambda) * (1 - cos(v_i, v_j))

The paper uses lambda = 0.5 by default. The returned similarity is
``sigma = 1 - d_lambda`` normalized to ``[0, 1]`` for interpretability.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.floating]


@dataclass(frozen=True, slots=True)
class SimilarPlayer:
    player_id: str
    similarity: float  # in [0, 1]
    euclidean: float
    cosine_similarity: float


def _euclidean(a: FloatArray, b: FloatArray) -> FloatArray:
    return np.linalg.norm(a - b, axis=-1)


def _cosine_sim(a: FloatArray, b: FloatArray) -> FloatArray:
    na = np.linalg.norm(a, axis=-1)
    nb = np.linalg.norm(b, axis=-1)
    denom = np.where((na * nb) > 1e-12, na * nb, 1e-12)
    return (a * b).sum(axis=-1) / denom


def hybrid_distance(
    query: FloatArray,
    candidates: FloatArray,
    lam: float = 0.5,
) -> tuple[FloatArray, FloatArray, FloatArray]:
    """Return (hybrid_distance, euclidean, cosine_similarity) for each candidate.

    The hybrid distance is normalized so the Euclidean and (1 - cos) terms are
    on comparable scales: Euclidean is divided by the max over candidates.
    """
    if not 0.0 <= lam <= 1.0:
        raise ValueError("lam must be in [0, 1]")
    if query.ndim != 1:
        raise ValueError("query must be 1-D")
    if candidates.ndim != 2 or candidates.shape[1] != query.shape[0]:
        raise ValueError("candidates must be (N, D) matching the query D")

    euc = _euclidean(candidates, query)
    euc_norm = euc / max(float(euc.max()), 1e-12)
    cos = _cosine_sim(candidates, query)
    cos_dist = 1.0 - cos
    hyb = lam * euc_norm + (1.0 - lam) * cos_dist
    return hyb, euc, cos


def knn_similar_players(
    query: FloatArray,
    candidates: FloatArray,
    candidate_ids: list[str],
    k: int = 10,
    lam: float = 0.5,
    exclude_ids: set[str] | None = None,
) -> list[SimilarPlayer]:
    """KNN retrieval in reduced feature space using the hybrid metric."""
    if k <= 0:
        raise ValueError("k must be > 0")
    if len(candidate_ids) != candidates.shape[0]:
        raise ValueError("candidate_ids length must match candidates rows")

    hyb, euc, cos = hybrid_distance(query, candidates, lam=lam)
    order = np.argsort(hyb)
    results: list[SimilarPlayer] = []
    for idx in order:
        pid = candidate_ids[idx]
        if exclude_ids and pid in exclude_ids:
            continue
        # map hybrid distance -> similarity in [0, 1]
        sim = max(0.0, 1.0 - float(hyb[idx]))
        results.append(
            SimilarPlayer(
                player_id=pid,
                similarity=sim,
                euclidean=float(euc[idx]),
                cosine_similarity=float(cos[idx]),
            )
        )
        if len(results) >= k:
            break
    return results

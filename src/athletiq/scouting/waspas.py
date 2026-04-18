"""Weighted Aggregated Sum Product Assessment — WASPAS (paper §4.4.2, Eq. 13).

    Q_ji = 0.5 * sum_c w_c * Y_bar_{jic} + 0.5 * prod_c Y_bar_{jic}^{w_c}

The multiplicative term penalizes categorical weaknesses; the additive term
captures average performance. ``Y_bar`` is the normalized performance matrix.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.floating]


def normalize_benefit(Y: FloatArray, axis: int = 0) -> FloatArray:
    """Linear "benefit" normalization: x / max (so higher is better)."""
    Y = np.asarray(Y, dtype=np.float64)
    m = Y.max(axis=axis, keepdims=True)
    m = np.where(m > 0, m, 1.0)
    return Y / m


def waspas_scores(
    Y: FloatArray,
    weights: FloatArray,
    epsilon: float = 1e-9,
) -> FloatArray:
    """Compute Q_j — a fitness score per row (player) for a single position.

    Parameters
    ----------
    Y : (N, C) normalized performance matrix (``Y_bar``). Values in (0, 1].
    weights : (C,) criteria weights (sum to 1).
    """
    Y = np.asarray(Y, dtype=np.float64)
    w = np.asarray(weights, dtype=np.float64)
    if Y.ndim != 2:
        raise ValueError("Y must be 2-D")
    if w.shape != (Y.shape[1],):
        raise ValueError("weights shape mismatch")
    if not np.isclose(w.sum(), 1.0, atol=1e-6):
        raise ValueError("weights must sum to 1")

    Y_safe = np.clip(Y, a_min=epsilon, a_max=None)
    additive = (Y_safe * w).sum(axis=1)
    multiplicative = np.prod(np.power(Y_safe, w), axis=1)
    return 0.5 * additive + 0.5 * multiplicative

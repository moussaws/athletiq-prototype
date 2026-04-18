"""Analytic Hierarchy Process — AHP (paper §4.4.1).

Given a pairwise comparison matrix ``A`` encoding a club's tactical priorities
over ``C`` KPIs:

    * the principal eigenvector (normalized to sum to 1) yields the weight
      vector ``w``;
    * consistency of ``A`` is validated via

          CR = (lambda_max - C) / ((C - 1) * RI)            (Eq. 12)

      and must satisfy ``CR < 0.10`` (Saaty 1980).
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.floating]

# Saaty random consistency indices for n=1..15
_RANDOM_INDEX = {
    1: 0.00,
    2: 0.00,
    3: 0.58,
    4: 0.90,
    5: 1.12,
    6: 1.24,
    7: 1.32,
    8: 1.41,
    9: 1.45,
    10: 1.49,
    11: 1.51,
    12: 1.54,
    13: 1.56,
    14: 1.57,
    15: 1.59,
}


def _validate_matrix(A: FloatArray) -> None:
    if A.ndim != 2 or A.shape[0] != A.shape[1]:
        raise ValueError(f"AHP matrix must be square; got {A.shape}")
    if (A <= 0).any():
        raise ValueError("AHP matrix entries must be positive (Saaty 1-9 scale)")
    # reciprocal check (lenient: within 1% tolerance)
    n = A.shape[0]
    for i in range(n):
        for j in range(n):
            expected = 1.0 / A[j, i]
            if abs(A[i, j] - expected) > 1e-6 + 0.01 * expected:
                raise ValueError(
                    f"AHP matrix not reciprocal at ({i},{j}): "
                    f"A[{i},{j}]={A[i, j]:.4f} vs 1/A[{j},{i}]={expected:.4f}"
                )


def ahp_weights(A: FloatArray) -> FloatArray:
    """Return the principal-eigenvector normalized weight vector."""
    A = np.asarray(A, dtype=np.float64)
    _validate_matrix(A)
    eigvals, eigvecs = np.linalg.eig(A)
    # Perron-Frobenius: pick the eigenvector for the largest real eigenvalue
    idx = int(np.argmax(eigvals.real))
    v = np.real(eigvecs[:, idx])
    # enforce positivity (flip if necessary)
    if (v < 0).all():
        v = -v
    if (v <= 0).any():
        # fall back to the geometric-mean of rows, which is always positive
        v = np.exp(np.log(A).mean(axis=1))
    return v / v.sum()


def consistency_ratio(A: FloatArray) -> float:
    """Compute CR (Eq. 12). ``CR < 0.10`` is considered consistent."""
    A = np.asarray(A, dtype=np.float64)
    _validate_matrix(A)
    n = A.shape[0]
    if n <= 2:
        return 0.0
    eigvals = np.linalg.eigvals(A).real
    lam_max = float(eigvals.max())
    ci = (lam_max - n) / (n - 1)
    ri = _RANDOM_INDEX.get(n)
    if ri is None or ri == 0:
        return 0.0
    return float(ci / ri)


def validate_consistency(A: FloatArray, threshold: float = 0.10) -> None:
    """Raise ``ValueError`` if CR >= threshold (club must revise preferences)."""
    cr = consistency_ratio(A)
    if cr >= threshold:
        raise ValueError(
            f"AHP matrix is inconsistent (CR={cr:.3f} >= {threshold}); "
            "please revise pairwise preferences."
        )

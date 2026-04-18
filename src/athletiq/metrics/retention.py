"""Press-Adjusted Absolute Ball Retention — PABR (paper §3.2, Eq. 5).

    PABR(j) = sum_s [ retained_s * exp(mean_P_s) ]  /  sum_s [ exp(mean_P_s) ]

Each possession sequence ``s`` has a binary retention outcome and a mean
collective pressure ``mean_P_s`` exerted on the carrier while they held the
ball. The exponential weighting means retention under high pressure is valued
exponentially more than safe retention.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class PossessionSequence:
    """One possession by a single player, aggregated over its frames."""

    mean_pressure: float
    retained: bool


def pabr(sequences: Sequence[PossessionSequence]) -> float:
    """Compute PABR. Returns 0.0 if there are no sequences."""
    if not sequences:
        return 0.0
    mean_P = np.array([s.mean_pressure for s in sequences], dtype=np.float64)
    retained = np.array([1.0 if s.retained else 0.0 for s in sequences], dtype=np.float64)
    # numerically stable exp-weight: subtract max to avoid overflow, cancels in ratio
    shift = float(mean_P.max())
    w = np.exp(mean_P - shift)
    num = float((retained * w).sum())
    den = float(w.sum())
    return num / den if den > 0 else 0.0

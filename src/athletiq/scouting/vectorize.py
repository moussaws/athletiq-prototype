"""Player vectorization (paper §4.1).

Every scouted player is encoded into a high-dimensional vector combining:

* traditional event metrics (passes, take-ons, shots, defensive actions, …)
* physical tracking indicators (accelerations, high-intensity sprint counts, …)
* AthletIQ deeptech indices (PABR, xT_carry, DDI)

Continuous variables are z-scored; missing values are imputed using
*position-specific* means (not global means, per the paper).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt
import pandas as pd

FloatArray = npt.NDArray[np.floating]


@dataclass(frozen=True, slots=True)
class PlayerVector:
    """Compact representation of a scouted player."""

    player_id: str
    name: str
    position: str
    nationality: str
    age: int
    market_value_m: float
    is_foreign: bool
    features: dict[str, float] = field(default_factory=dict)

    def as_series(self) -> pd.Series:
        return pd.Series({"player_id": self.player_id, **self.features})


def build_feature_matrix(
    players: list[PlayerVector],
    feature_names: list[str] | None = None,
) -> tuple[pd.DataFrame, FloatArray]:
    """Stack players into a (N, D) matrix with z-scoring + position-wise imputation.

    Returns
    -------
    meta : DataFrame indexed by player_id with (name, position, ...) columns
    X    : (N, D) float array, z-scored, NaN-free
    """
    if not players:
        raise ValueError("players is empty")

    rows = []
    meta_rows = []
    for p in players:
        rows.append({"player_id": p.player_id, **p.features})
        meta_rows.append(
            {
                "player_id": p.player_id,
                "name": p.name,
                "position": p.position,
                "nationality": p.nationality,
                "age": p.age,
                "market_value_m": p.market_value_m,
                "is_foreign": p.is_foreign,
            }
        )
    df = pd.DataFrame(rows).set_index("player_id")
    meta = pd.DataFrame(meta_rows).set_index("player_id")

    if feature_names is not None:
        df = df.reindex(columns=feature_names)

    # position-specific mean imputation
    df = df.copy()
    positions = meta["position"].values
    for pos in np.unique(positions):
        mask = positions == pos
        pos_mean = df.iloc[mask].mean(numeric_only=True)
        df.iloc[mask] = df.iloc[mask].fillna(pos_mean)
    # fall back to global mean for any leftover NaNs
    df = df.fillna(df.mean(numeric_only=True))
    df = df.fillna(0.0)

    # z-score (protect against zero-std columns)
    mu = df.mean()
    sigma = df.std(ddof=0).replace(0.0, 1.0)
    Z = (df - mu) / sigma
    return meta, Z.to_numpy(dtype=np.float64)

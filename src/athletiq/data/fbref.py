"""Load the committed FBRef Big-5 2023-24 cohort as PlayerVectors.

The CSV at ``src/athletiq/data/fbref/big5_2023_24.csv`` is pre-processed
by ``scripts/build_fbref_big5_2023_24.py`` from the
``conalhenderson/football-data-warehouse`` Kaggle dataset (CC0 license).
All features are per-match (divided by 90-minute equivalents) so they are
directly comparable to the synthetic cohort the prototype shipped with.

FBRef does not publish tracking-derived signals (sprints /
accelerations). ``sprint_count`` and ``accel_count`` are therefore
modeled as proxies of on-ball activity (progressive carries, successful
take-ons, att-third touches) rather than the raw GPS counts used in the
synthetic generator. Similarly ``ddi`` is a proxy combining att-pen-area
touches, take-ons, and carry threat. Both are flagged in the dataset
banner exposed to the coach via ``FBRefCohort.provenance``.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

from athletiq.scouting.vectorize import PlayerVector

CSV_PATH = Path(__file__).resolve().parent / "fbref" / "big5_2023_24.csv"

PROXY_FEATURES: frozenset[str] = frozenset({"sprint_count", "accel_count", "ddi"})


@dataclass(frozen=True, slots=True)
class FBRefCohort:
    players: tuple[PlayerVector, ...]
    provenance: dict[str, object]

    @property
    def as_list(self) -> list[PlayerVector]:
        return list(self.players)


def _row_to_vector(row: pd.Series) -> PlayerVector:
    nation = str(row["nation_code"])
    features = {
        "passes_completed": float(row["passes_completed_per90"]),
        "take_ons": float(row["take_ons_per90"]),
        "shots": float(row["shots_per90"]),
        "tackles": float(row["tackles_per90"]),
        "interceptions": float(row["interceptions_per90"]),
        "aerial_duels_won": float(row["aerials_won_per90"]),
        "sprint_count": float(row["sprint_count_proxy"]),
        "accel_count": float(row["accel_count_proxy"]),
        "pabr": float(row["pabr"]),
        "xt_carry": float(row["xt_carry"]),
        "ddi": float(row["ddi_proxy"]),
    }
    return PlayerVector(
        player_id=str(row["player_id"]),
        name=str(row["player"]),
        position=str(row["position_role"]),
        nationality=nation,
        age=int(row["age"]) if pd.notna(row["age"]) else 25,
        market_value_m=float(row["market_value_m"]),
        is_foreign=bool(int(row["is_foreign"])),
        features=features,
    )


@lru_cache(maxsize=1)
def load_fbref_cohort(path: Path | None = None) -> FBRefCohort:
    """Load the committed CSV into a cohort of ``PlayerVector``s.

    Raises ``FileNotFoundError`` if the CSV is missing so callers can
    fall back to the synthetic generator if desired.
    """
    csv = path or CSV_PATH
    if not csv.exists():
        raise FileNotFoundError(csv)
    df = pd.read_csv(csv)
    players = tuple(_row_to_vector(r) for _, r in df.iterrows())
    provenance = {
        "source": "FBRef Big-5 2023-24 via football-data-warehouse (Kaggle, CC0)",
        "season": "2023-24",
        "n_players": len(players),
        "competitions": sorted(df["comp"].unique().tolist()),
        "min_minutes_filter": 900,
        "market_value_real": int((df["market_value_source"] == "transfermarkt").sum()),
        "market_value_imputed": int((df["market_value_source"] == "imputed").sum()),
        "proxy_features": sorted(PROXY_FEATURES),
        "proxy_note": (
            "sprint_count and accel_count are proxies of on-ball activity "
            "(progressive carries, take-ons, att-third touches) because FBRef "
            "does not publish tracking-derived GPS signals. ddi is a proxy of "
            "dangerous-area activity built from att-pen touches, take-ons, "
            "and carry threat."
        ),
    }
    return FBRefCohort(players=players, provenance=provenance)

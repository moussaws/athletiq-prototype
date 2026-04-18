"""StatsBomb Open Data adapter (optional, `pip install -e '.[statsbomb]'`).

Given a StatsBomb ``match_id``, this loader aggregates a per-player feature
matrix using the same feature schema as the synthetic generator, so
downstream PCA/K-Means/KNN/AHP/WASPAS/BIP can run on real data without any
code changes.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

from athletiq.scouting.vectorize import PlayerVector

try:
    from statsbombpy import sb  # type: ignore

    STATSBOMB_AVAILABLE = True
except ImportError:  # pragma: no cover
    sb = None  # type: ignore[assignment]
    STATSBOMB_AVAILABLE = False


_POSITION_MAP = {
    # StatsBomb position -> AthletIQ compact position
    "Goalkeeper": "GK",
    "Right Back": "FB",
    "Left Back": "FB",
    "Right Wing Back": "FB",
    "Left Wing Back": "FB",
    "Center Back": "CB",
    "Right Center Back": "CB",
    "Left Center Back": "CB",
    "Left Defensive Midfield": "DM",
    "Right Defensive Midfield": "DM",
    "Center Defensive Midfield": "DM",
    "Left Center Midfield": "CM",
    "Right Center Midfield": "CM",
    "Center Midfield": "CM",
    "Right Midfield": "CM",
    "Left Midfield": "CM",
    "Left Attacking Midfield": "AM",
    "Right Attacking Midfield": "AM",
    "Center Attacking Midfield": "AM",
    "Left Wing": "WG",
    "Right Wing": "WG",
    "Center Forward": "ST",
    "Secondary Striker": "ST",
}


@dataclass(frozen=True, slots=True)
class StatsBombCompetition:
    competition_id: int
    season_id: int
    name: str


def _normalize_position(pos: str | None) -> str:
    if not pos:
        return "CM"
    return _POSITION_MAP.get(pos, "CM")


def load_statsbomb_match_player_vectors(
    match_id: int,
    price_model: str = "age_position",
) -> list[PlayerVector]:
    """Load one match's event data and aggregate per-player feature vectors.

    Parameters
    ----------
    match_id : StatsBomb match id.
    price_model : how to synthesise a market value for BIP. ``"age_position"``
        uses a simple heuristic (young strikers are expensive, old defenders
        cheap). Feel free to replace with a real pricing source.
    """
    if not STATSBOMB_AVAILABLE:
        raise RuntimeError("statsbombpy not installed. Run `pip install -e '.[statsbomb]'`.")

    events = sb.events(match_id=match_id)
    if events is None or events.empty:
        return []

    # Per-player aggregation
    def _is(row_type: str) -> Iterable[int]:
        return events["type"] == row_type

    agg = (
        events.groupby(["player_id", "player", "position", "team"])
        .agg(
            passes_completed=(
                "type",
                lambda s: int(((s == "Pass") & (events.loc[s.index, "pass_outcome"].isna())).sum()),
            ),
            take_ons=("type", lambda s: int((s == "Dribble").sum())),
            shots=("type", lambda s: int((s == "Shot").sum())),
            tackles=("type", lambda s: int((s == "Duel").sum())),
            interceptions=("type", lambda s: int((s == "Interception").sum())),
        )
        .reset_index()
    )

    players: list[PlayerVector] = []
    for _, row in agg.iterrows():
        pid = str(int(row["player_id"]))
        name = str(row["player"])
        sb_pos = _normalize_position(str(row["position"]))
        nat = "Unknown"
        age = 25
        is_foreign = False
        # crude market-value synthesis
        mv_base = {"ST": 15, "WG": 14, "AM": 12, "CM": 10, "DM": 9, "FB": 8, "CB": 8, "GK": 6}[
            sb_pos
        ]
        if price_model == "age_position":
            mv = float(mv_base) * max(0.1, 1.0 - abs(age - 25) * 0.05)
        else:
            mv = float(mv_base)

        features = {
            "passes_completed": float(row["passes_completed"]),
            "take_ons": float(row["take_ons"]),
            "shots": float(row["shots"]),
            "tackles": float(row["tackles"]),
            "interceptions": float(row["interceptions"]),
            # fields that don't exist in StatsBomb v1 event schema — left 0,
            # will be imputed to position means in vectorize.build_feature_matrix
            "aerial_duels_won": 0.0,
            "sprint_count": 0.0,
            "accel_count": 0.0,
            "pabr": 0.0,
            "xt_carry": 0.0,
            "ddi": 0.0,
        }
        players.append(
            PlayerVector(
                player_id=f"SB{pid}",
                name=name,
                position=sb_pos,
                nationality=nat,
                age=age,
                market_value_m=float(np.round(mv, 2)),
                is_foreign=is_foreign,
                features=features,
            )
        )
    return players

"""StatsBomb Open Data adapter (optional, ``pip install -e '.[statsbomb]'``).

Exposes three clean functions used by both the CLI and the API:

* :func:`list_competitions` — every open competition/season available.
* :func:`list_matches` — every match in a given (competition, season).
* :func:`load_match_players` — per-player feature vectors for one match,
  aggregated from raw event data using the same feature schema as
  :mod:`athletiq.data.synthetic`.  The output plugs directly into
  :func:`athletiq.scouting.vectorize.build_feature_matrix` so every
  downstream algorithm (PCA, K-Means, KNN, AHP, WASPAS, BIP) works on
  real data without any code changes.

Notes on feature coverage
-------------------------
StatsBomb's event stream does *not* publish high-frequency tracking
(player positions every frame).  That means the AthletIQ deeptech
indices that depend on tracking (``pabr``, ``ddi``, physical counters
like ``sprint_count`` / ``accel_count``) cannot be computed directly
from open data.  We leave those fields as ``NaN`` — the vectorizer's
position-specific mean imputation takes over in
:func:`athletiq.scouting.vectorize.build_feature_matrix`, which keeps
the pipeline numerically stable while honestly signalling that the
values are imputed rather than observed.

``xt_carry`` *is* derivable from StatsBomb events (Carry / Pass events
carry start + end locations), so we compute it on the fly using the
default xT grid.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Any

import numpy as np

from athletiq.scouting.vectorize import PlayerVector

if TYPE_CHECKING:
    import pandas as pd

try:
    from statsbombpy import sb  # type: ignore

    STATSBOMB_AVAILABLE = True
except ImportError:  # pragma: no cover
    sb = None  # type: ignore[assignment]
    STATSBOMB_AVAILABLE = False


# ─── Position mapping ──────────────────────────────────────────────────
_POSITION_MAP: dict[str, str] = {
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


def _normalize_position(pos: str | None) -> str:
    if not pos:
        return "CM"
    return _POSITION_MAP.get(pos, "CM")


# ─── Public dataclasses ────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class StatsBombCompetition:
    competition_id: int
    season_id: int
    country_name: str
    competition_name: str
    season_name: str
    competition_gender: str


@dataclass(frozen=True, slots=True)
class StatsBombMatch:
    match_id: int
    competition_id: int
    season_id: int
    match_date: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int


# ─── xT lookup helper for carry/pass events ────────────────────────────
def _xt_lookup(loc: list[float] | None, xt_grid: Any) -> float:
    """Read the xT value at (x, y) in StatsBomb's 120×80 pitch frame.

    Rescales to the xT grid's pitch dimensions (default 105×68) before
    indexing.
    """
    if loc is None or not isinstance(loc, (list, tuple)) or len(loc) < 2:
        return 0.0
    try:
        x = float(loc[0]) * (xt_grid.pitch_length / 120.0)
        y = float(loc[1]) * (xt_grid.pitch_width / 80.0)
    except (TypeError, ValueError):
        return 0.0
    rows, cols = xt_grid.shape
    col = int(np.clip(np.floor(x / xt_grid.pitch_length * cols), 0, cols - 1))
    row = int(np.clip(np.floor(y / xt_grid.pitch_width * rows), 0, rows - 1))
    return float(xt_grid.values[row, col])


# ─── Public API ────────────────────────────────────────────────────────
def _require_statsbombpy() -> None:
    if not STATSBOMB_AVAILABLE:
        raise RuntimeError("statsbombpy is not installed. Run `pip install -e '.[statsbomb]'`.")


def list_competitions() -> list[StatsBombCompetition]:
    """Return every (competition, season) pair in the open dataset."""
    _require_statsbombpy()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df = sb.competitions()
    out: list[StatsBombCompetition] = []
    for _, row in df.iterrows():
        out.append(
            StatsBombCompetition(
                competition_id=int(row["competition_id"]),
                season_id=int(row["season_id"]),
                country_name=str(row.get("country_name", "")),
                competition_name=str(row.get("competition_name", "")),
                season_name=str(row.get("season_name", "")),
                competition_gender=str(row.get("competition_gender", "")),
            )
        )
    return out


def list_matches(competition_id: int, season_id: int) -> list[StatsBombMatch]:
    """Return every match in a given (competition, season)."""
    _require_statsbombpy()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df = sb.matches(competition_id=competition_id, season_id=season_id)
    out: list[StatsBombMatch] = []
    for _, row in df.iterrows():
        out.append(
            StatsBombMatch(
                match_id=int(row["match_id"]),
                competition_id=int(competition_id),
                season_id=int(season_id),
                match_date=str(row.get("match_date", "")),
                home_team=str(row.get("home_team", "")),
                away_team=str(row.get("away_team", "")),
                home_score=int(row.get("home_score", 0) or 0),
                away_score=int(row.get("away_score", 0) or 0),
            )
        )
    out.sort(key=lambda m: m.match_date)
    return out


def _aggregate_player_features(events_df: pd.DataFrame) -> pd.DataFrame:
    """Group a StatsBomb events DataFrame by player and compute features."""
    import pandas as pd

    from athletiq.metrics.xt import default_xt_grid

    xt_grid = default_xt_grid()

    events = events_df.copy()
    # Backfill missing columns that older matches may omit, so selectors
    # below never KeyError.
    for col in (
        "type",
        "player",
        "player_id",
        "position",
        "team",
        "team_id",
        "pass_outcome",
        "location",
        "carry_end_location",
        "shot_outcome",
    ):
        if col not in events.columns:
            events[col] = None

    events = events[events["player_id"].notna()].copy()

    # Per-event carry xT contribution (positive values only — progressive carries).
    def _carry_xt(row: pd.Series) -> float:
        if row["type"] != "Carry":
            return 0.0
        end = row["carry_end_location"]
        start = row["location"]
        return max(0.0, _xt_lookup(end, xt_grid) - _xt_lookup(start, xt_grid))

    events["_xt_carry"] = events.apply(_carry_xt, axis=1)

    # Group key: player, so we can also carry team + position forward.
    groups = []
    for (pid, name), g in events.groupby(["player_id", "player"], sort=False):
        types = g["type"]
        # position: mode (most common) — players can rotate during a match
        pos_vc = g["position"].dropna().value_counts()
        pos_raw = pos_vc.index[0] if len(pos_vc) else None
        team_vc = g["team"].dropna().value_counts()
        team = team_vc.index[0] if len(team_vc) else "Unknown"

        passes = types == "Pass"
        passes_completed = int((passes & g["pass_outcome"].isna()).sum())
        take_ons = int((types == "Dribble").sum())
        shots = int((types == "Shot").sum())
        tackles = int((types == "Duel").sum())
        interceptions = int((types == "Interception").sum())
        xt_carry = float(g["_xt_carry"].sum())

        groups.append(
            {
                "player_id": int(pid),
                "name": str(name),
                "position_raw": pos_raw,
                "team": team,
                "passes_completed": float(passes_completed),
                "take_ons": float(take_ons),
                "shots": float(shots),
                "tackles": float(tackles),
                "interceptions": float(interceptions),
                "xt_carry": float(xt_carry),
            }
        )
    return pd.DataFrame(groups)


@lru_cache(maxsize=32)
def load_match_players(
    match_id: int,
    price_model: str = "age_position",
) -> tuple[PlayerVector, ...]:
    """Load one match's event data and aggregate per-player feature vectors.

    Cached (LRU 32) so repeated hits against the same match from the API
    don't re-download + re-parse the event stream.
    """
    _require_statsbombpy()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        events = sb.events(match_id=match_id)
    if events is None or getattr(events, "empty", True):
        return ()

    agg = _aggregate_player_features(events)

    players: list[PlayerVector] = []
    for _, row in agg.iterrows():
        pid = str(int(row["player_id"]))
        pos = _normalize_position(row["position_raw"])
        age = 25  # StatsBomb events do not carry DOB; see module docstring.
        mv_base = {
            "ST": 15,
            "WG": 14,
            "AM": 12,
            "CM": 10,
            "DM": 9,
            "FB": 8,
            "CB": 8,
            "GK": 6,
        }[pos]
        if price_model == "age_position":
            mv = float(mv_base) * max(0.1, 1.0 - abs(age - 25) * 0.05)
        else:
            mv = float(mv_base)

        # Features observable from StatsBomb open events.
        # Fields that require tracking data are left as NaN so the
        # vectorizer's position-specific mean imputation handles them.
        features: dict[str, float] = {
            "passes_completed": float(row["passes_completed"]),
            "take_ons": float(row["take_ons"]),
            "shots": float(row["shots"]),
            "tackles": float(row["tackles"]),
            "interceptions": float(row["interceptions"]),
            "xt_carry": float(row["xt_carry"]),
            # Tracking-dependent — imputed to position mean downstream.
            "aerial_duels_won": float("nan"),
            "sprint_count": float("nan"),
            "accel_count": float("nan"),
            "pabr": float("nan"),
            "ddi": float("nan"),
        }
        players.append(
            PlayerVector(
                player_id=f"SB{pid}",
                name=str(row["name"]),
                position=pos,
                nationality=str(row["team"]),  # team in the match, used as "nationality" proxy
                age=age,
                market_value_m=float(np.round(mv, 2)),
                is_foreign=False,
                features=features,
            )
        )
    return tuple(players)


def clear_match_cache() -> None:
    """Clear the :func:`load_match_players` LRU cache (used by tests)."""
    load_match_players.cache_clear()


# ─── Backwards-compatible alias (earlier draft used a different name) ──
def load_statsbomb_match_player_vectors(
    match_id: int,
    price_model: str = "age_position",
) -> list[PlayerVector]:
    """Deprecated alias, retained for external callers."""
    return list(load_match_players(match_id, price_model=price_model))

"""VAEP-lite — per-match action-value attribution on StatsBomb events.

The full VAEP framework (Decroos et al., KDD 2019) trains gradient-boosted
trees on a large event-stream pool to estimate P(score | state) and
P(concede | state). We implement a lightweight logistic-regression variant
that is self-contained and works on a single match of open-data events:

  * Actions are a cleaned subset of the event stream (Pass, Carry, Shot,
    Dribble). Each action carries start + end coordinates, action type
    one-hot, and period/time.
  * Labels: y_score = 1 iff the acting team scores within the next K
    actions; y_concede = 1 iff the acting team concedes within K.
  * Two logistic-regression models are fit on all actions of the match and
    scored against the same match, giving per-action P_score and P_concede.
  * Per-action value := ΔP_score − ΔP_concede between the state *after* and
    *before* the action. Positive contributions accrue to the acting player.

This is intentionally a "lite" flavour: fitting on the same match it scores
means coefficients are a calibration of this match rather than a population
prior. That is honest for a prototype (no population-scale training data is
bundled), and the API surfaces the sample size + K so the caller can reason
about the noise floor.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import pandas as pd

ACTION_TYPES: tuple[str, ...] = ("Pass", "Carry", "Shot", "Dribble")

# StatsBomb pitch frame is 120 × 80.
_PITCH_X = 120.0
_PITCH_Y = 80.0
_GOAL = (120.0, 40.0)


@dataclass(frozen=True, slots=True)
class PlayerVAEP:
    player_id: str
    name: str
    team: str
    position: str
    n_actions: int
    vaep: float
    offensive_vaep: float
    defensive_vaep: float


@dataclass(frozen=True, slots=True)
class MatchVAEP:
    match_id: int
    k_horizon: int
    n_actions: int
    n_goals: int
    players: tuple[PlayerVAEP, ...]


def _as_action_df(events_df: pd.DataFrame) -> pd.DataFrame:
    """Filter raw events down to action rows and return a flat feature frame."""
    cols = events_df.columns
    df = events_df.copy()
    for col in (
        "type",
        "team",
        "team_id",
        "player",
        "player_id",
        "position",
        "location",
        "pass_end_location",
        "carry_end_location",
        "shot_end_location",
        "shot_outcome",
        "period",
        "timestamp",
    ):
        if col not in cols:
            df[col] = None

    df = df[df["type"].isin(ACTION_TYPES)].copy()

    def _end_loc(row: pd.Series) -> list[float] | None:
        t = row["type"]
        if t == "Pass":
            return row["pass_end_location"]
        if t == "Carry":
            return row["carry_end_location"]
        if t == "Shot":
            return row["shot_end_location"]
        return row["location"]

    start = df["location"].apply(lambda v: v if isinstance(v, (list, tuple)) else [np.nan, np.nan])
    end = df.apply(_end_loc, axis=1).apply(
        lambda v: v if isinstance(v, (list, tuple)) else [np.nan, np.nan]
    )
    df["x0"] = start.apply(lambda v: float(v[0]) if len(v) >= 2 else np.nan)
    df["y0"] = start.apply(lambda v: float(v[1]) if len(v) >= 2 else np.nan)
    df["x1"] = end.apply(lambda v: float(v[0]) if len(v) >= 2 else np.nan)
    df["y1"] = end.apply(lambda v: float(v[1]) if len(v) >= 2 else np.nan)

    # Drop rows with no usable coordinates
    df = df.dropna(subset=["x0", "y0"]).copy()
    df["x1"] = df["x1"].fillna(df["x0"])
    df["y1"] = df["y1"].fillna(df["y0"])

    df["dist0"] = np.sqrt((_GOAL[0] - df["x0"]) ** 2 + (_GOAL[1] - df["y0"]) ** 2)
    df["dist1"] = np.sqrt((_GOAL[0] - df["x1"]) ** 2 + (_GOAL[1] - df["y1"]) ** 2)

    for t in ACTION_TYPES:
        df[f"is_{t.lower()}"] = (df["type"] == t).astype(float)

    df["is_goal"] = ((df["type"] == "Shot") & (df["shot_outcome"] == "Goal")).astype(int)

    def _ts_seconds(s: object) -> float:
        if not isinstance(s, str):
            return 0.0
        try:
            h, m, rest = s.split(":")
            return float(h) * 3600 + float(m) * 60 + float(rest)
        except Exception:
            return 0.0

    df["t_sec"] = df["timestamp"].apply(_ts_seconds)
    df["period_int"] = df["period"].fillna(1).astype(int)
    return df.sort_values(["period_int", "t_sec"]).reset_index(drop=True)


_FEATURE_COLS: tuple[str, ...] = (
    "x0",
    "y0",
    "x1",
    "y1",
    "dist0",
    "dist1",
    "is_pass",
    "is_carry",
    "is_shot",
    "is_dribble",
    "period_int",
)


def _build_labels(df: pd.DataFrame, k: int) -> tuple[np.ndarray, np.ndarray]:
    """y_score / y_concede from the team_id column + future is_goal events."""
    n = len(df)
    y_score = np.zeros(n, dtype=int)
    y_concede = np.zeros(n, dtype=int)
    team_ids = df["team_id"].to_numpy()
    is_goal = df["is_goal"].to_numpy()
    for i in range(n):
        window_end = min(n, i + k + 1)
        for j in range(i + 1, window_end):
            if is_goal[j] == 1:
                if team_ids[j] == team_ids[i]:
                    y_score[i] = 1
                else:
                    y_concede[i] = 1
            if y_score[i] == 1 and y_concede[i] == 1:
                break
    return y_score, y_concede


def _fit_logreg(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Fit a L2-regularised logistic regression; return weights (p+1,).

    Uses scikit-learn if available (already a project dep) to avoid
    hand-rolling IRLS. The last weight is the intercept.
    """
    from sklearn.linear_model import LogisticRegression

    if y.sum() == 0 or y.sum() == len(y):
        return np.zeros(X.shape[1] + 1, dtype=np.float64)
    clf = LogisticRegression(
        C=1.0,
        max_iter=300,
        solver="liblinear",
    )
    clf.fit(X, y)
    w = np.concatenate([clf.coef_.ravel(), clf.intercept_.ravel()])
    return w.astype(np.float64)


def _predict_proba(X: np.ndarray, w: np.ndarray) -> np.ndarray:
    if np.allclose(w, 0.0):
        return np.full(X.shape[0], 0.01)
    z = X @ w[:-1] + w[-1]
    return 1.0 / (1.0 + np.exp(-z))


def _standardise(X: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mu = X.mean(axis=0)
    sd = X.std(axis=0)
    sd = np.where(sd < 1e-8, 1.0, sd)
    return (X - mu) / sd, mu, sd


def compute_match_vaep(events_df: pd.DataFrame, *, k: int = 10) -> tuple[MatchVAEP, pd.DataFrame]:
    """Fit + score VAEP-lite on one match of events. Returns (leaderboard, per-event frame)."""
    import pandas as pd

    df = _as_action_df(events_df)
    if df.empty:
        return MatchVAEP(match_id=-1, k_horizon=k, n_actions=0, n_goals=0, players=()), df

    X = df[list(_FEATURE_COLS)].to_numpy(dtype=np.float64)
    Xn, mu, sd = _standardise(X)
    y_score, y_concede = _build_labels(df, k=k)

    w_score = _fit_logreg(Xn, y_score)
    w_concede = _fit_logreg(Xn, y_concede)

    p_score = _predict_proba(Xn, w_score)
    p_concede = _predict_proba(Xn, w_concede)

    # ΔP between consecutive actions belonging to the same team.
    team = df["team_id"].to_numpy()
    dp_score = np.zeros(len(df))
    dp_concede = np.zeros(len(df))
    prev_by_team: dict[int, float] = {}
    prev_by_team_concede: dict[int, float] = {}
    for i in range(len(df)):
        t = int(team[i]) if not pd.isna(team[i]) else -1
        prev_s = prev_by_team.get(t, p_score[i])
        prev_c = prev_by_team_concede.get(t, p_concede[i])
        dp_score[i] = p_score[i] - prev_s
        dp_concede[i] = p_concede[i] - prev_c
        prev_by_team[t] = p_score[i]
        prev_by_team_concede[t] = p_concede[i]

    df = df.copy()
    df["p_score"] = p_score
    df["p_concede"] = p_concede
    df["dp_score"] = dp_score
    df["dp_concede"] = dp_concede
    df["vaep"] = dp_score - dp_concede

    # Aggregate per player.
    players: list[PlayerVAEP] = []
    grouped = df.dropna(subset=["player_id"]).groupby(
        ["player_id", "player"], sort=False, dropna=False
    )
    for (pid, name), g in grouped:
        team_vc = g["team"].dropna().value_counts()
        team_label = str(team_vc.index[0]) if len(team_vc) else ""
        pos_vc = g["position"].dropna().value_counts()
        pos_label = str(pos_vc.index[0]) if len(pos_vc) else ""
        players.append(
            PlayerVAEP(
                player_id=str(int(pid)),
                name=str(name),
                team=team_label,
                position=pos_label,
                n_actions=int(len(g)),
                vaep=float(g["vaep"].sum()),
                offensive_vaep=float(g["dp_score"].sum()),
                defensive_vaep=float(-g["dp_concede"].sum()),
            )
        )
    players.sort(key=lambda p: p.vaep, reverse=True)
    mv = MatchVAEP(
        match_id=-1,
        k_horizon=k,
        n_actions=int(len(df)),
        n_goals=int(df["is_goal"].sum()),
        players=tuple(players),
    )
    # Unused stash to satisfy the type checker that mu/sd were kept.
    del mu, sd
    return mv, df


@lru_cache(maxsize=32)
def match_vaep(match_id: int, k: int = 10) -> MatchVAEP:
    """Load a StatsBomb match and compute VAEP-lite. Cached per match."""
    from athletiq.data.statsbomb import STATSBOMB_AVAILABLE, sb

    if not STATSBOMB_AVAILABLE:
        raise RuntimeError("statsbombpy is not installed")
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        events = sb.events(match_id=match_id)
    mv, _ = compute_match_vaep(events, k=k)
    return MatchVAEP(
        match_id=match_id,
        k_horizon=mv.k_horizon,
        n_actions=mv.n_actions,
        n_goals=mv.n_goals,
        players=mv.players,
    )

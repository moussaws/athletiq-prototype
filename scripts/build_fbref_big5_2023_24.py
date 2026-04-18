"""Build the committed FBRef Big-5 2023-24 cohort CSV.

Reads the `conalhenderson/football-data-warehouse` Kaggle dataset (CC0
license), filters to season=2024 (2023-24 campaign), joins the standard /
defense / passing / possession / shooting / misc tables on the composite
(player, squad, comp, season) key, merges the Transfermarkt valuations
table on (player, squad, season), and writes a per-player feature frame
to `src/athletiq/data/fbref/big5_2023_24.csv`.

Run once to refresh the committed CSV. The runtime loader in
`athletiq.data.fbref` consumes only the committed CSV — no network calls
at request time.

Usage:
    pip install pandas kagglehub
    python scripts/build_fbref_big5_2023_24.py

The dataset DOI: https://www.kaggle.com/datasets/conalhenderson/football-data-warehouse
"""

from __future__ import annotations

import math
from pathlib import Path

import kagglehub
import numpy as np
import pandas as pd

OUTPUT = Path(__file__).resolve().parent.parent / "src/athletiq/data/fbref/big5_2023_24.csv"
MIN_MINUTES = 900
SEASON = 2024  # 2023-24 season (ending year)

COMP_TO_LEAGUE_NATION: dict[str, str] = {
    "Premier League": "ENG",
    "La Liga": "ESP",
    "Serie A": "ITA",
    "Bundesliga": "GER",
    "Ligue 1": "FRA",
}


def _slug(name: str, squad: str) -> str:
    s = "".join(c.lower() if c.isalnum() else "-" for c in f"{name}-{squad}").strip("-")
    while "--" in s:
        s = s.replace("--", "-")
    return s


def _classify_position(
    position: str,
    goals_xg_per_90: float,
    tackles_int_per_90: float,
    progressive_carries_per_90: float,
    att_third_touches_per_90: float,
    df_att_third_threshold: float,
) -> str:
    """Map FBRef multi-label position strings into the 8-role taxonomy.

    FBRef only tags primary + optional secondary macro-role
    (GK/DF/MF/FW). Sub-roles are derived from secondary signals:
    FB = defender with an attacking footprint (top-quartile
    att-third touches/90 or secondary MF/FW tag); AM/DM splits on
    goal threat vs defensive action per 90; WG splits on progressive
    carries per 90.
    """
    if not isinstance(position, str):
        return "CM"
    labels = [p.strip() for p in position.split(",") if p.strip()]
    primary = labels[0] if labels else ""
    secondary = labels[1] if len(labels) > 1 else ""
    if primary == "GK":
        return "GK"
    if primary == "DF":
        if secondary in {"MF", "FW"}:
            return "FB"
        if att_third_touches_per_90 >= df_att_third_threshold:
            return "FB"
        return "CB"
    if primary == "MF":
        if secondary == "FW" or goals_xg_per_90 >= 0.35:
            return "AM"
        if tackles_int_per_90 >= 3.0:
            return "DM"
        return "CM"
    if primary == "FW":
        if secondary == "MF" or progressive_carries_per_90 >= 3.5:
            return "WG"
        return "ST"
    return "CM"


def _impute_market_value(row: pd.Series) -> float:
    age = float(row.get("age") or 25.0)
    ga_score = float(
        (row.get("goals") or 0)
        + (row.get("assists") or 0)
        + (row.get("xg") or 0)
        + (row.get("xag") or 0)
    )
    def_score = float((row.get("tackles") or 0) + (row.get("interceptions") or 0))
    passes = float(row.get("passes_completed") or 0)
    raw = 2.0 + 2.5 * ga_score + 0.08 * def_score + 0.02 * passes
    age_factor = math.exp(-((age - 25.0) ** 2) / 60.0)
    return round(max(0.3, raw * age_factor), 2)


def _normalize_nation(nation: str) -> str:
    if not isinstance(nation, str):
        return "UNK"
    parts = nation.split()
    return parts[-1].upper() if parts else "UNK"


def _build() -> pd.DataFrame:
    path = kagglehub.dataset_download("conalhenderson/football-data-warehouse")
    base = Path(path)

    standard = pd.read_csv(base / "player_standard_stats.csv", low_memory=False)
    defense = pd.read_csv(base / "player_defense.csv", low_memory=False)
    passing = pd.read_csv(base / "player_passing.csv", low_memory=False)
    possession = pd.read_csv(base / "player_possession.csv", low_memory=False)
    shooting = pd.read_csv(base / "player_shooting.csv", low_memory=False)
    misc = pd.read_csv(base / "player_misc.csv", low_memory=False)
    valuations = pd.read_csv(base / "valuations.csv", low_memory=False)

    key_cols = ["player", "squad", "comp", "season"]

    standard = standard[standard.season == SEASON].copy()
    defense = defense[defense.season == SEASON][[*key_cols, "tackles", "interceptions"]].copy()
    passing = passing[passing.season == SEASON][
        [*key_cols, "passes_completed", "passes_attempted", "pass_completion_pct"]
    ].copy()
    possession = possession[possession.season == SEASON][
        [
            *key_cols,
            "take_ons_attempted",
            "take_ons_successful",
            "carries",
            "att_pen_area_touches",
            "att_third_touches",
        ]
    ].copy()
    shooting = shooting[shooting.season == SEASON][[*key_cols, "shots", "shots_on_target"]].copy()
    misc = misc[misc.season == SEASON][[*key_cols, "aerials_won"]].copy()

    df = standard.merge(defense, on=key_cols, how="left")
    df = df.merge(passing, on=key_cols, how="left")
    df = df.merge(possession, on=key_cols, how="left")
    df = df.merge(shooting, on=key_cols, how="left")
    df = df.merge(misc, on=key_cols, how="left")

    df = df[df["min"] >= MIN_MINUTES].copy()

    val24 = valuations[valuations.season == SEASON][
        ["player", "squad", "market_value_eur_mill"]
    ].copy()
    df = df.merge(val24, on=["player", "squad"], how="left")

    nineties = df["ninety_mins_played"].replace({0: np.nan})
    ga_per_90 = (df["goals"].fillna(0) + df["xg"].fillna(0) + df["xag"].fillna(0)) / nineties
    def_per_90 = (df["tackles"].fillna(0) + df["interceptions"].fillna(0)) / nineties
    prgc_per_90 = df["progressive_carries"].fillna(0) / nineties
    att3_per_90 = df["att_third_touches"].fillna(0) / nineties
    ga_per_90 = ga_per_90.fillna(0.0)
    def_per_90 = def_per_90.fillna(0.0)
    prgc_per_90 = prgc_per_90.fillna(0.0)
    att3_per_90 = att3_per_90.fillna(0.0)

    is_df_primary = df["position"].fillna("").str.split(",").str[0].str.strip() == "DF"
    df_att3_threshold = (
        float(att3_per_90[is_df_primary].quantile(0.65)) if is_df_primary.any() else 20.0
    )

    df["position_role"] = [
        _classify_position(p, g, d, c, a3, df_att3_threshold)
        for p, g, d, c, a3 in zip(
            df["position"], ga_per_90, def_per_90, prgc_per_90, att3_per_90, strict=True
        )
    ]

    df["passes_completed_per90"] = (df["passes_completed"].fillna(0) / nineties).fillna(0.0)
    df["take_ons_per90"] = (df["take_ons_successful"].fillna(0) / nineties).fillna(0.0)
    df["shots_per90"] = (df["shots"].fillna(0) / nineties).fillna(0.0)
    df["tackles_per90"] = (df["tackles"].fillna(0) / nineties).fillna(0.0)
    df["interceptions_per90"] = (df["interceptions"].fillna(0) / nineties).fillna(0.0)
    df["aerials_won_per90"] = (df["aerials_won"].fillna(0) / nineties).fillna(0.0)
    df["progressive_carries_per90"] = prgc_per_90
    df["touches_att_third_per90"] = (df["att_third_touches"].fillna(0) / nineties).fillna(0.0)
    df["pabr"] = (df["pass_completion_pct"].fillna(0) / 100.0).clip(0.0, 1.0)
    df["xt_carry"] = (
        0.5 * df["progressive_carries_per90"]
        + 0.25 * (df["att_pen_area_touches"].fillna(0) / nineties).fillna(0.0)
        + 0.25 * df["shots_per90"]
    )

    sprint_proxy = df["progressive_carries_per90"] + 0.3 * df["take_ons_per90"]
    accel_proxy = df["touches_att_third_per90"] + 0.5 * df["progressive_carries_per90"]
    df["sprint_count_proxy"] = sprint_proxy.round(2)
    df["accel_count_proxy"] = accel_proxy.round(2)

    att_pen_per90 = (df["att_pen_area_touches"].fillna(0) / nineties).fillna(0.0)
    df["ddi_proxy"] = (
        10.0 * att_pen_per90 + 4.0 * df["take_ons_per90"] + 20.0 * df["xt_carry"]
    ).round(2)

    df["nation_code"] = df["nation"].apply(_normalize_nation)
    df["league_nation"] = df["comp"].map(COMP_TO_LEAGUE_NATION).fillna("UNK")
    df["is_foreign"] = (df["nation_code"] != df["league_nation"]).astype(int)

    df["market_value_m"] = df.apply(
        lambda r: (
            float(r["market_value_eur_mill"])
            if pd.notna(r["market_value_eur_mill"]) and float(r["market_value_eur_mill"]) > 0
            else _impute_market_value(r)
        ),
        axis=1,
    )
    df["market_value_source"] = np.where(
        df["market_value_eur_mill"].notna() & (df["market_value_eur_mill"] > 0),
        "transfermarkt",
        "imputed",
    )

    df["player_id"] = [_slug(n, s) for n, s in zip(df["player"], df["squad"], strict=True)]
    df["player_id"] = df["player_id"].where(
        ~df["player_id"].duplicated(keep="first"),
        df["player_id"] + "-" + df.groupby("player_id").cumcount().astype(str),
    )

    out_cols = [
        "player_id",
        "player",
        "squad",
        "comp",
        "nation_code",
        "league_nation",
        "position",
        "position_role",
        "age",
        "min",
        "ninety_mins_played",
        "goals",
        "assists",
        "xg",
        "xag",
        "passes_completed",
        "pass_completion_pct",
        "passes_completed_per90",
        "pabr",
        "take_ons_attempted",
        "take_ons_successful",
        "take_ons_per90",
        "shots",
        "shots_on_target",
        "shots_per90",
        "tackles",
        "tackles_per90",
        "interceptions",
        "interceptions_per90",
        "aerials_won",
        "aerials_won_per90",
        "progressive_carries",
        "progressive_carries_per90",
        "touches_att_third_per90",
        "xt_carry",
        "sprint_count_proxy",
        "accel_count_proxy",
        "ddi_proxy",
        "market_value_m",
        "market_value_source",
        "is_foreign",
    ]
    return df[out_cols].sort_values(["position_role", "player"]).reset_index(drop=True)


def main() -> None:
    df = _build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT, index=False)
    print(f"Wrote {len(df)} rows to {OUTPUT}")
    print("Per-role counts:\n", df["position_role"].value_counts())
    print(
        f"Market value: {(df['market_value_source'] == 'transfermarkt').sum()} real, "
        f"{(df['market_value_source'] == 'imputed').sum()} imputed"
    )


if __name__ == "__main__":
    main()

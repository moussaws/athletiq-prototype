"""Coach-facing recruit brief — plain-English playstyles → WASPAS ranked shortlist.

Instead of asking a coach to pick raw features and build a pairwise matrix, this
route accepts a short brief ("press-resistant DM under €5M, under 28") and
translates it to a criteria / weights pair, runs WASPAS across the filtered
cohort (same machinery as /api/squad), and returns the top N candidates with a
one-line "why they fit" verdict each.

The playstyle → weights translation table lives here rather than in
``athletiq.scouting`` so scouting stays a math library and this module owns the
product-level vocabulary.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from athletiq.api.state import _default_feature_names, get_store
from athletiq.scouting.waspas import normalize_benefit, waspas_scores

router = APIRouter()


Playstyle = Literal[
    "ball_winner",
    "progressor",
    "press_resistant",
    "box_to_box",
    "finisher",
]


# Each preset lists the 5 criteria that define the style and a weight vector
# summing to 1. The lead criterion gets ~35%, support criteria split the rest.
# These were hand-tuned so a coach who picks "finisher" gets a striker-shaped
# shortlist, not a ball-playing CB.
PLAYSTYLE_PRESETS: dict[str, dict[str, object]] = {
    "ball_winner": {
        "label": "Ball-winner",
        "description": (
            "Breaks play up — tackles, interceptions, and dangerous recoveries. "
            "Looks for the defender who bails the midfield out."
        ),
        "criteria": [
            "tackles",
            "interceptions",
            "ddi",
            "aerial_duels_won",
            "sprint_count",
        ],
        "weights": [0.30, 0.30, 0.20, 0.12, 0.08],
    },
    "progressor": {
        "label": "Progressor",
        "description": (
            "Moves the ball forward through dangerous zones — carry xT, "
            "pressure-resistance, take-ons, passes completed."
        ),
        "criteria": [
            "xt_carry",
            "pabr",
            "take_ons",
            "passes_completed",
            "accel_count",
        ],
        "weights": [0.32, 0.25, 0.18, 0.15, 0.10],
    },
    "press_resistant": {
        "label": "Press-resistant",
        "description": (
            "Retains possession under pressure — completion rate under duress, "
            "retention, and short-range carries out of trouble."
        ),
        "criteria": [
            "passes_completed",
            "pabr",
            "xt_carry",
            "take_ons",
            "ddi",
        ],
        "weights": [0.32, 0.28, 0.18, 0.12, 0.10],
    },
    "box_to_box": {
        "label": "Box-to-box",
        "description": (
            "High-volume engine — covers ground at speed in both directions, "
            "contributes with the ball and without it."
        ),
        "criteria": [
            "sprint_count",
            "accel_count",
            "passes_completed",
            "tackles",
            "xt_carry",
        ],
        "weights": [0.28, 0.22, 0.20, 0.18, 0.12],
    },
    "finisher": {
        "label": "Finisher",
        "description": (
            "Final-third output — shots, dangerous carries, and accelerations into the box."
        ),
        "criteria": [
            "shots",
            "xt_carry",
            "take_ons",
            "pabr",
            "accel_count",
        ],
        "weights": [0.35, 0.25, 0.18, 0.12, 0.10],
    },
}


class PlaystyleInfo(BaseModel):
    key: str
    label: str
    description: str
    criteria: list[str]
    weights: list[float]


class PlaystyleCatalog(BaseModel):
    playstyles: list[PlaystyleInfo]


@router.get("/playstyles", response_model=PlaystyleCatalog)
def list_playstyles() -> PlaystyleCatalog:
    return PlaystyleCatalog(
        playstyles=[
            PlaystyleInfo(
                key=k,
                label=str(v["label"]),
                description=str(v["description"]),
                criteria=list(v["criteria"]),  # type: ignore[arg-type]
                weights=list(v["weights"]),  # type: ignore[arg-type]
            )
            for k, v in PLAYSTYLE_PRESETS.items()
        ]
    )


class RecruitBrief(BaseModel):
    position: str = Field(..., description="GK/CB/FB/DM/CM/AM/WG/ST")
    playstyle: Playstyle
    max_age: int | None = Field(default=None, ge=15, le=45)
    max_value_m: float | None = Field(default=None, gt=0)
    limit: int = Field(default=10, ge=1, le=50)


class RecruitCandidate(BaseModel):
    player_id: str
    name: str
    position: str
    nationality: str
    age: int
    market_value_m: float
    is_foreign: bool
    fit_score: float
    fit_summary: str
    top_trait: str
    top_trait_value: float


class RecruitResponse(BaseModel):
    position: str
    playstyle: str
    playstyle_label: str
    criteria: list[str]
    weights: list[float]
    candidates: list[RecruitCandidate]
    pool_size: int
    headline: str


def _trait_phrase(feature: str) -> str:
    return {
        "passes_completed": "passes completed",
        "take_ons": "take-ons",
        "shots": "shots",
        "tackles": "tackles",
        "interceptions": "interceptions",
        "aerial_duels_won": "aerial duels won",
        "sprint_count": "sprints",
        "accel_count": "accelerations",
        "pabr": "pressure-adjusted ball retention",
        "xt_carry": "carry xT",
        "ddi": "dangerous-defensive index (m²)",
    }.get(feature, feature)


def _verdict(
    player_name: str,
    top_trait_label: str,
    top_trait_value: float,
    fit_score: float,
) -> str:
    return (
        f"{player_name} fits at {fit_score * 100:.0f}% of the style — "
        f"leads with {top_trait_value:.2f} {top_trait_label}."
    )


@router.post("/search", response_model=RecruitResponse)
def recruit_search(brief: RecruitBrief) -> RecruitResponse:
    store = get_store()
    preset = PLAYSTYLE_PRESETS.get(brief.playstyle)
    if preset is None:
        raise HTTPException(status_code=422, detail=f"unknown playstyle: {brief.playstyle}")

    feature_names = _default_feature_names()
    criteria = list(preset["criteria"])  # type: ignore[arg-type]
    weights = np.array(list(preset["weights"]), dtype=np.float64)  # type: ignore[arg-type]
    # Validate that every preset criterion is a known feature.
    missing = [c for c in criteria if c not in feature_names]
    if missing:
        raise HTTPException(
            status_code=500, detail=f"preset references unknown features: {missing}"
        )

    # Filter to position first, then apply age/value caps.
    pool = [p for p in store.players if p.position == brief.position]
    if brief.max_age is not None:
        pool = [p for p in pool if p.age <= brief.max_age]
    if brief.max_value_m is not None:
        pool = [p for p in pool if p.market_value_m <= brief.max_value_m]

    if not pool:
        raise HTTPException(
            status_code=404,
            detail=(
                f"no players match position={brief.position} "
                f"max_age={brief.max_age} max_value_m={brief.max_value_m}"
            ),
        )

    raw = np.array(
        [[p.features.get(fn, 0.0) for fn in criteria] for p in pool],
        dtype=np.float64,
    )
    Y_norm = normalize_benefit(raw)
    scores = waspas_scores(Y_norm, weights)

    order = np.argsort(-scores)[: brief.limit]
    candidates: list[RecruitCandidate] = []
    for idx in order.tolist():
        p = pool[idx]
        # Top trait = the criterion with the highest normalized * weight
        # contribution to this player's score — answers "why did they come up?"
        contribs = Y_norm[idx] * weights
        top_i = int(np.argmax(contribs))
        top_feature = criteria[top_i]
        top_value = float(raw[idx, top_i])
        candidates.append(
            RecruitCandidate(
                player_id=p.player_id,
                name=p.name,
                position=p.position,
                nationality=p.nationality,
                age=p.age,
                market_value_m=p.market_value_m,
                is_foreign=p.is_foreign,
                fit_score=float(scores[idx]),
                fit_summary=_verdict(
                    p.name,
                    _trait_phrase(top_feature),
                    top_value,
                    float(scores[idx]),
                ),
                top_trait=_trait_phrase(top_feature),
                top_trait_value=top_value,
            )
        )

    label = str(preset["label"])
    if candidates:
        top = candidates[0]
        headline = (
            f"Top {brief.position} for a {label.lower()} brief: "
            f"{top.name} ({top.fit_score * 100:.0f}% fit)."
        )
    else:
        headline = f"No {brief.position} matches for a {label.lower()} brief."

    return RecruitResponse(
        position=brief.position,
        playstyle=brief.playstyle,
        playstyle_label=label,
        criteria=criteria,
        weights=weights.tolist(),
        candidates=candidates,
        pool_size=len(pool),
        headline=headline,
    )

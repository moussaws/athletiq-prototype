"""Map raw numbers → coach-readable sentences.

Every function here takes plain floats / small dicts so the callers can decide
whether to cache reference distributions or recompute per-request. Nothing
mutates the optimizer / metrics / CV layers; this is a pure presentation
helper.
"""

from __future__ import annotations

from dataclasses import dataclass

# Verbal band thresholds — based on standard-normal percentiles so the phrasing
# lines up with how coaches talk about "top 10%", "above average", etc.
_PERCENTILE_BANDS = (
    (95.0, "elite"),
    (80.0, "strong"),
    (60.0, "above average"),
    (40.0, "average"),
    (20.0, "below average"),
    (0.0, "weak"),
)

# Feature → short coach phrase, used when verbalising a player's top traits.
_FEATURE_PHRASE = {
    "passes_completed": "progressive passing",
    "take_ons": "1-v-1 dribbling",
    "shots": "goal threat",
    "tackles": "tackle volume",
    "interceptions": "reading of the game",
    "aerial_duels_won": "aerial dominance",
    "sprint_count": "high-intensity running",
    "accel_count": "explosiveness",
    "pabr": "ball retention under pressure",
    "xt_carry": "carrying into dangerous areas",
    "ddi": "space creation in the final third",
}


@dataclass(frozen=True)
class MetricVerdict:
    headline: str  # one sentence, coach-facing
    value: float
    percentile: float | None  # 0–100, None if no reference pool
    band: str  # "elite" | "strong" | ... | "weak"


def _percentile(value: float, pool: list[float]) -> float:
    """Percentile rank of ``value`` inside ``pool`` (0-100, inclusive)."""
    if not pool:
        return 50.0
    n = len(pool)
    below = sum(1 for v in pool if v < value)
    equal = sum(1 for v in pool if v == value)
    return (below + 0.5 * equal) / n * 100.0


def _band_for(percentile: float) -> str:
    for threshold, label in _PERCENTILE_BANDS:
        if percentile >= threshold:
            return label
    return "weak"


def percentile_verdict(value: float, pool: list[float]) -> tuple[float, str]:
    """Return (percentile, band) for ``value`` in ``pool``."""
    p = _percentile(value, pool)
    return p, _band_for(p)


def describe_metric(
    name: str,
    value: float,
    pool: list[float] | None = None,
    unit: str = "",
) -> MetricVerdict:
    """Turn a raw metric into a coach-facing one-liner + percentile band.

    ``pool`` lets us say "top 10% vs peers". If omitted we still produce a
    usable headline but report percentile=None and band="average".
    """
    phrase = _FEATURE_PHRASE.get(name, name.replace("_", " "))
    if pool:
        p, band = percentile_verdict(value, pool)
        pct_str = f"top {round(100 - p)}%" if p >= 50 else f"bottom {round(p)}%"
        headline = f"{phrase.capitalize()}: {band} — {pct_str} of peers ({value:.2f}{unit})."
        return MetricVerdict(headline=headline, value=value, percentile=p, band=band)
    headline = f"{phrase.capitalize()}: {value:.2f}{unit}."
    return MetricVerdict(headline=headline, value=value, percentile=None, band="average")


def describe_ddi(ddi_m2: float, actions: int) -> str:
    """Plain-English verdict for a player's match-level DDI aggregate."""
    if actions <= 0:
        return "No on-ball actions in dangerous zones this match."
    avg = ddi_m2 / actions
    if ddi_m2 >= 600:
        tier = "Elite space-creator"
    elif ddi_m2 >= 300:
        tier = "Consistent threat"
    elif ddi_m2 >= 100:
        tier = "Occasional threat"
    else:
        tier = "Low impact in final third"
    return f"{tier}: {ddi_m2:.0f} m² of dangerous space created across {actions} actions (avg {avg:.1f} m²/action)."


def describe_player_style(
    position: str,
    features: dict[str, float],
    reference: dict[str, tuple[float, float]],
    top_n: int = 3,
) -> str:
    """One-sentence style summary grounded in the player's strongest features."""
    ranked: list[tuple[str, float]] = []
    for feat, value in features.items():
        if feat not in reference:
            continue
        mean, std = reference[feat]
        if std <= 1e-9:
            continue
        z = (value - mean) / std
        ranked.append((feat, z))
    ranked.sort(key=lambda kv: kv[1], reverse=True)
    highlights = [
        _FEATURE_PHRASE.get(feat, feat.replace("_", " "))
        for feat, z in ranked[:top_n]
        if z > 0.3  # ignore "strong" features that are actually just average
    ]
    if not highlights:
        return f"A balanced {position} profile with no standout traits vs peers."
    if len(highlights) == 1:
        return f"{position} whose calling card is {highlights[0]}."
    return f"{position} profile built around {', '.join(highlights[:-1])} and {highlights[-1]}."

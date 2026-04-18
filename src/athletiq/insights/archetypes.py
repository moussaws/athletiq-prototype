"""Archetype labeler — maps a position + cluster centroid to a football role.

The paper (§3.3) motivates clusters like *Deep-Lying Playmaker* vs *Box-to-Box
Raider*. This module formalises that taxonomy per position: each position has
a palette of candidate archetypes with a "signature" (which features should be
high or low relative to the position's reference distribution). A centroid is
scored against every candidate; the best match wins.

Scoring is a weighted sum of signed z-scores on the signature features, so
the label reflects *direction* as well as magnitude (e.g. a centroid with a
low ``passes_completed`` z-score actively *counts against* "Deep-Lying
Playmaker").
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Side = Literal["hi", "lo"]


@dataclass(frozen=True)
class ArchetypeLabel:
    """Human-readable role for a cluster centroid."""

    name: str
    description: str
    key_traits: list[str]


@dataclass(frozen=True)
class _Candidate:
    name: str
    description: str
    signature: dict[str, tuple[Side, float]]  # feature -> (side, weight)
    key_traits: list[str]


# Archetype palettes per position. Sources: paper §3.3 (Deep-Lying Playmaker,
# Box-to-Box Raider) + well-established tactical roles (Regista, Trequartista,
# Target Man, Poacher, False 9, Inverted Winger, ...).
_PALETTE: dict[str, list[_Candidate]] = {
    "GK": [
        _Candidate(
            "Sweeper-Keeper",
            "Plays high off the line, initiates attacks with short passing.",
            {"passes_completed": ("hi", 1.0), "pabr": ("hi", 0.6)},
            ["Distribution under pressure", "Proactive line"],
        ),
        _Candidate(
            "Traditional Shot-Stopper",
            "Stays on the line, commands the box aerially.",
            {"aerial_duels_won": ("hi", 0.8), "passes_completed": ("lo", 0.5)},
            ["Command of the area", "Pure shot-stopping"],
        ),
    ],
    "CB": [
        _Candidate(
            "Ball-Playing Defender",
            "Starts build-up from deep with line-breaking passes.",
            {"passes_completed": ("hi", 1.0), "xt_carry": ("hi", 0.8), "pabr": ("hi", 0.4)},
            ["Progressive passing", "Composure on the ball"],
        ),
        _Candidate(
            "Stopper",
            "Aggressive, wins duels high up the pitch.",
            {"aerial_duels_won": ("hi", 0.8), "tackles": ("hi", 0.8), "ddi": ("lo", 0.3)},
            ["Duels & aerial dominance", "Front-foot defending"],
        ),
        _Candidate(
            "Cover Defender",
            "Reads the game and sweeps behind the line.",
            {"interceptions": ("hi", 1.0), "sprint_count": ("hi", 0.6)},
            ["Interceptions", "Recovery pace"],
        ),
    ],
    "FB": [
        _Candidate(
            "Attacking Full-Back",
            "Overlaps high, contributes carries into the final third.",
            {"xt_carry": ("hi", 1.0), "sprint_count": ("hi", 0.6), "take_ons": ("hi", 0.4)},
            ["Overlapping runs", "Final-third entries"],
        ),
        _Candidate(
            "Defensive Full-Back",
            "Stays compact, prioritises the back four's shape.",
            {"tackles": ("hi", 0.8), "interceptions": ("hi", 0.8), "xt_carry": ("lo", 0.6)},
            ["Defensive solidity", "Positional discipline"],
        ),
        _Candidate(
            "Inverted Full-Back",
            "Tucks inside in possession to form a back-three / double pivot.",
            {"passes_completed": ("hi", 1.0), "xt_carry": ("hi", 0.4), "sprint_count": ("lo", 0.3)},
            ["Central rotations", "Possession link"],
        ),
    ],
    "DM": [
        _Candidate(
            "Regista",
            "Deep-lying metronome — dictates tempo with long ranges of pass.",
            {"passes_completed": ("hi", 1.0), "xt_carry": ("hi", 0.5), "pabr": ("hi", 0.4)},
            ["Deep playmaking", "Long-range passing"],
        ),
        _Candidate(
            "Ball-Winner (Destroyer)",
            "Screens the back line, breaks play with tackles and interceptions.",
            {"tackles": ("hi", 1.0), "interceptions": ("hi", 1.0), "passes_completed": ("lo", 0.3)},
            ["Tackles / interceptions", "Screening role"],
        ),
        _Candidate(
            "Anchor",
            "Stays in front of the back line with minimal vertical risk.",
            {"interceptions": ("hi", 0.7), "xt_carry": ("lo", 0.8), "take_ons": ("lo", 0.5)},
            ["Low-risk positioning", "Shape protection"],
        ),
    ],
    "CM": [
        _Candidate(
            "Deep-Lying Playmaker",
            "Drops in to receive and dictate the game with short progression.",
            {"passes_completed": ("hi", 1.0), "xt_carry": ("hi", 0.6), "sprint_count": ("lo", 0.3)},
            ["Central progression", "Tempo control"],
        ),
        _Candidate(
            "Box-to-Box Raider",
            "Covers every blade — presses, carries, arrives in the box.",
            {"sprint_count": ("hi", 1.0), "xt_carry": ("hi", 0.6), "tackles": ("hi", 0.6)},
            ["Engine / high mileage", "End-to-end influence"],
        ),
        _Candidate(
            "Mezzala",
            "Operates in the half-spaces, combines and arrives late.",
            {"xt_carry": ("hi", 1.0), "take_ons": ("hi", 0.6), "shots": ("hi", 0.4)},
            ["Half-space runs", "Third-man combinations"],
        ),
    ],
    "AM": [
        _Candidate(
            "Trequartista",
            "Free role behind the striker — chance creation over pressing.",
            {"xt_carry": ("hi", 1.0), "take_ons": ("hi", 0.8), "tackles": ("lo", 0.4)},
            ["Chance creation", "Between-lines reception"],
        ),
        _Candidate(
            "Shadow Striker",
            "Ghosts into the box, arrives on the second ball.",
            {"shots": ("hi", 1.0), "xt_carry": ("hi", 0.4), "sprint_count": ("hi", 0.4)},
            ["Goal threat from deep", "Late box runs"],
        ),
        _Candidate(
            "Creative 10",
            "Classic attacking midfielder — combines, threads the eye of the needle.",
            {"passes_completed": ("hi", 1.0), "xt_carry": ("hi", 0.5)},
            ["Final pass", "Combination play"],
        ),
    ],
    "WG": [
        _Candidate(
            "Inside Forward",
            "Cuts in from the flank onto their stronger foot, shoots / combines centrally.",
            {"shots": ("hi", 1.0), "xt_carry": ("hi", 0.6), "take_ons": ("hi", 0.4)},
            ["Shots from wide channels", "Inside drifts"],
        ),
        _Candidate(
            "Touchline Winger",
            "Holds width, beats the full-back, delivers from the byline.",
            {"take_ons": ("hi", 1.0), "sprint_count": ("hi", 0.8), "shots": ("lo", 0.3)},
            ["1-v-1 dribbling", "Width & crosses"],
        ),
        _Candidate(
            "Inverted Winger",
            "Drifts inside to combine and feed overlapping full-backs.",
            {"passes_completed": ("hi", 0.8), "xt_carry": ("hi", 0.6), "take_ons": ("lo", 0.4)},
            ["Central rotations", "Combination play"],
        ),
    ],
    "ST": [
        _Candidate(
            "Target Man",
            "Holds up play, wins aerial duels, finishes off crosses.",
            {"aerial_duels_won": ("hi", 1.0), "shots": ("hi", 0.5), "take_ons": ("lo", 0.4)},
            ["Aerial presence", "Hold-up play"],
        ),
        _Candidate(
            "Poacher",
            "Lives in the box — high shot volume, minimal build-up involvement.",
            {"shots": ("hi", 1.0), "passes_completed": ("lo", 0.6), "xt_carry": ("lo", 0.3)},
            ["Penalty-box finisher", "Off-the-shoulder runs"],
        ),
        _Candidate(
            "False 9",
            "Drops between the lines, links play, drags centre-backs out.",
            {"passes_completed": ("hi", 1.0), "xt_carry": ("hi", 0.6), "shots": ("lo", 0.4)},
            ["Dropping movement", "Link-up play"],
        ),
    ],
}


def _zscore(value: float, ref_mean: float, ref_std: float) -> float:
    if ref_std <= 1e-9:
        return 0.0
    return (value - ref_mean) / ref_std


def _score_candidate(
    candidate: _Candidate,
    centroid: dict[str, float],
    reference: dict[str, tuple[float, float]],
) -> float:
    score = 0.0
    for feature, (side, weight) in candidate.signature.items():
        if feature not in centroid or feature not in reference:
            continue
        ref_mean, ref_std = reference[feature]
        z = _zscore(centroid[feature], ref_mean, ref_std)
        if side == "lo":
            z = -z
        score += weight * z
    return score


def label_archetype(
    position: str,
    centroid: dict[str, float],
    reference: dict[str, tuple[float, float]],
) -> ArchetypeLabel:
    """Pick the best-fit archetype label for a cluster centroid.

    ``reference`` is ``{feature: (mean, std)}`` computed across all players at
    the same position, so z-scores reflect how this cluster deviates from its
    positional peers.
    """
    palette = _PALETTE.get(position)
    if not palette:
        return ArchetypeLabel(
            name=f"{position} (cluster)",
            description="No archetype taxonomy defined for this position yet.",
            key_traits=[],
        )
    best = max(palette, key=lambda c: _score_candidate(c, centroid, reference))
    return ArchetypeLabel(
        name=best.name,
        description=best.description,
        key_traits=list(best.key_traits),
    )


def available_archetypes(position: str) -> list[str]:
    """Return the full palette of archetype names for a position (for UI)."""
    return [c.name for c in _PALETTE.get(position, [])]

"""Synthetic data generators used by unit tests, demos, and UI seeds.

Nothing in this module touches the network — every function is
fully deterministic given a ``seed``.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import numpy as np

from athletiq.metrics.pitch_control import PlayerSnapshot
from athletiq.metrics.types import PITCH_LENGTH_M, PITCH_WIDTH_M
from athletiq.scouting.vectorize import PlayerVector

POSITIONS: tuple[str, ...] = ("GK", "CB", "FB", "DM", "CM", "AM", "WG", "ST")

ARCHETYPES: dict[str, dict[str, tuple[float, float]]] = {
    # (mean, std) per feature, per position — sized for realistic z-distribution
    "GK": {
        "passes_completed": (18, 6),
        "take_ons": (0.1, 0.3),
        "shots": (0.0, 0.1),
        "tackles": (0.3, 0.5),
        "interceptions": (1.2, 0.8),
        "aerial_duels_won": (2.5, 1.2),
        "sprint_count": (4, 2),
        "accel_count": (10, 4),
        "pabr": (0.92, 0.04),
        "xt_carry": (0.02, 0.02),
        "ddi": (5, 5),
    },
    "CB": {
        "passes_completed": (62, 12),
        "take_ons": (0.4, 0.5),
        "shots": (0.2, 0.3),
        "tackles": (2.2, 1.0),
        "interceptions": (2.1, 1.0),
        "aerial_duels_won": (4.3, 1.5),
        "sprint_count": (9, 3),
        "accel_count": (28, 8),
        "pabr": (0.85, 0.06),
        "xt_carry": (0.05, 0.03),
        "ddi": (15, 10),
    },
    "FB": {
        "passes_completed": (48, 10),
        "take_ons": (1.2, 0.7),
        "shots": (0.4, 0.4),
        "tackles": (1.8, 0.9),
        "interceptions": (1.6, 0.8),
        "aerial_duels_won": (1.8, 0.9),
        "sprint_count": (22, 5),
        "accel_count": (55, 10),
        "pabr": (0.82, 0.06),
        "xt_carry": (0.12, 0.06),
        "ddi": (28, 14),
    },
    "DM": {
        "passes_completed": (72, 12),
        "take_ons": (0.7, 0.5),
        "shots": (0.5, 0.4),
        "tackles": (2.6, 1.0),
        "interceptions": (2.4, 1.0),
        "aerial_duels_won": (2.4, 1.0),
        "sprint_count": (14, 4),
        "accel_count": (48, 9),
        "pabr": (0.88, 0.05),
        "xt_carry": (0.11, 0.05),
        "ddi": (32, 15),
    },
    "CM": {
        "passes_completed": (68, 12),
        "take_ons": (1.6, 0.8),
        "shots": (0.8, 0.5),
        "tackles": (1.8, 0.8),
        "interceptions": (1.6, 0.8),
        "aerial_duels_won": (1.6, 0.9),
        "sprint_count": (16, 4),
        "accel_count": (52, 9),
        "pabr": (0.90, 0.05),
        "xt_carry": (0.18, 0.07),
        "ddi": (55, 25),
    },
    "AM": {
        "passes_completed": (52, 10),
        "take_ons": (2.5, 1.1),
        "shots": (1.6, 0.8),
        "tackles": (0.9, 0.5),
        "interceptions": (0.9, 0.5),
        "aerial_duels_won": (1.0, 0.7),
        "sprint_count": (20, 5),
        "accel_count": (55, 10),
        "pabr": (0.87, 0.06),
        "xt_carry": (0.28, 0.1),
        "ddi": (70, 30),
    },
    "WG": {
        "passes_completed": (36, 8),
        "take_ons": (3.8, 1.3),
        "shots": (1.8, 0.8),
        "tackles": (0.9, 0.5),
        "interceptions": (0.7, 0.4),
        "aerial_duels_won": (1.0, 0.7),
        "sprint_count": (28, 6),
        "accel_count": (68, 12),
        "pabr": (0.80, 0.07),
        "xt_carry": (0.32, 0.12),
        "ddi": (60, 28),
    },
    "ST": {
        "passes_completed": (22, 6),
        "take_ons": (2.2, 1.0),
        "shots": (3.1, 1.1),
        "tackles": (0.4, 0.3),
        "interceptions": (0.3, 0.3),
        "aerial_duels_won": (2.8, 1.1),
        "sprint_count": (26, 6),
        "accel_count": (60, 11),
        "pabr": (0.78, 0.07),
        "xt_carry": (0.22, 0.1),
        "ddi": (40, 22),
    },
}

NATIONALITIES: tuple[str, ...] = (
    "Egypt",
    "Morocco",
    "Tunisia",
    "Algeria",
    "Nigeria",
    "Senegal",
    "Brazil",
    "Argentina",
    "Spain",
    "France",
    "Germany",
    "Portugal",
    "England",
    "Italy",
    "Netherlands",
    "Belgium",
)

DOMESTIC_NATIONALITY = "Egypt"


def generate_synthetic_cohort(n: int = 200, seed: int = 42) -> list[PlayerVector]:
    """Build ``n`` synthetic players spread across positions/nationalities."""
    rng = np.random.default_rng(seed)
    py_rng = random.Random(seed)
    players: list[PlayerVector] = []
    for i in range(n):
        position = POSITIONS[i % len(POSITIONS)]
        spec = ARCHETYPES[position]
        feats = {k: float(max(0.0, rng.normal(mu, sig))) for k, (mu, sig) in spec.items()}
        nat = py_rng.choice(NATIONALITIES)
        age = int(py_rng.randint(17, 34))
        market_value = round(float(max(0.05, rng.lognormal(mean=0.6, sigma=1.2))), 2)
        is_foreign = nat != DOMESTIC_NATIONALITY
        players.append(
            PlayerVector(
                player_id=f"P{i:04d}",
                name=f"Player {i:04d}",
                position=position,
                nationality=nat,
                age=age,
                market_value_m=market_value,
                is_foreign=is_foreign,
                features=feats,
            )
        )
    return players


@dataclass(frozen=True, slots=True)
class SyntheticPossession:
    carrier_pos: list[tuple[float, float]]
    defenders_pos: list[list[tuple[float, float]]]
    retained: bool


def generate_synthetic_possession(
    n_frames: int = 40,
    n_defenders: int = 3,
    retained: bool = True,
    pressure_level: float = 0.6,
    seed: int = 0,
) -> SyntheticPossession:
    """Build a realistic possession at a given pressure level.

    ``pressure_level`` in [0, 1] pushes defenders closer to the carrier.
    """
    rng = np.random.default_rng(seed)
    # carrier walks a short, slightly curved path near the centre
    start = np.array([50.0, 34.0])
    direction = rng.normal(0, 1, size=2)
    direction /= max(np.linalg.norm(direction), 1e-6)
    carrier = [tuple(start + direction * (i * 0.15)) for i in range(n_frames)]

    # defenders orbit at a radius that shrinks with pressure_level
    radius = 4.5 - 3.5 * pressure_level
    defenders_per_frame: list[list[tuple[float, float]]] = []
    base_angles = rng.uniform(0, 2 * np.pi, size=n_defenders)
    for i in range(n_frames):
        frame_def: list[tuple[float, float]] = []
        for k in range(n_defenders):
            theta = base_angles[k] + i * 0.03
            r = radius + rng.normal(0, 0.3)
            fx, fy = carrier[i]
            frame_def.append(
                (
                    float(fx + r * np.cos(theta)),
                    float(fy + r * np.sin(theta)),
                )
            )
        defenders_per_frame.append(frame_def)
    return SyntheticPossession(
        carrier_pos=carrier,
        defenders_pos=defenders_per_frame,
        retained=retained,
    )


def generate_synthetic_snapshot(seed: int = 0) -> list[PlayerSnapshot]:
    """Build a realistic 11v11 instantaneous snapshot for Pitch Control demos."""
    rng = np.random.default_rng(seed)
    players: list[PlayerSnapshot] = []

    # Attacking team (team=0): 4-3-3ish shape centred in opponent half
    attack_positions = [
        (10, 34),  # GK
        (30, 10),
        (30, 24),
        (30, 44),
        (30, 58),
        (55, 20),
        (55, 34),
        (55, 48),
        (80, 16),
        (85, 34),
        (80, 52),
    ]
    for x, y in attack_positions:
        jitter = rng.normal(0, 1.5, size=2)
        vel = rng.normal(0, 1.2, size=2)
        players.append(
            PlayerSnapshot(
                x=float(x + jitter[0]),
                y=float(y + jitter[1]),
                vx=float(vel[0]),
                vy=float(vel[1]),
                team=0,
            )
        )

    # Defending team (team=1): mirrored 4-4-2ish block
    defense_positions = [
        (95, 34),
        (75, 10),
        (75, 24),
        (75, 44),
        (75, 58),
        (55, 14),
        (55, 28),
        (55, 40),
        (55, 54),
        (35, 24),
        (35, 44),
    ]
    for x, y in defense_positions:
        jitter = rng.normal(0, 1.5, size=2)
        vel = rng.normal(0, 1.2, size=2)
        players.append(
            PlayerSnapshot(
                x=float(x + jitter[0]),
                y=float(y + jitter[1]),
                vx=float(vel[0]),
                vy=float(vel[1]),
                team=1,
            )
        )
    return players


# keep the pitch constants importable from here
__all__ = [
    "ARCHETYPES",
    "NATIONALITIES",
    "PITCH_LENGTH_M",
    "PITCH_WIDTH_M",
    "POSITIONS",
    "SyntheticPossession",
    "generate_synthetic_cohort",
    "generate_synthetic_possession",
    "generate_synthetic_snapshot",
]

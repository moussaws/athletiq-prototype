"""Per-player DDI attribution over a synthetic match.

DDI (paper §3.4, Eq. 8) is defined at the *possession* level:

    DDI = integral over {x : xT(x) >= tau} [Phi_{t+}(x) - Phi_{t-}(x)] dx

…which tells you how much high-threat space the attacking team generated
between two snapshots. On its own this is a collective metric.

To turn DDI into a per-player product (leaderboards, player cards), we need
an *attribution* scheme that credits individual attackers for the high-xT
space they opened up. We use a "single-mover" attribution:

1. Simulate a match as a sequence of N off-ball actions.
2. In each action, exactly one attacker is the designated mover — they
   shift forward by a small vector into the final third; the other 21
   players stay put.
3. The DDI computed between the before- and after-snapshots is credited
   entirely to that mover.
4. Aggregating across N actions yields per-player match DDI (m^2) plus
   an action count.

This is a prototype-grade attribution. Full leave-one-out and Shapley-style
attribution (where several players move simultaneously) is a v2 seam.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from athletiq.metrics.ddi import DEFAULT_TAU, ddi
from athletiq.metrics.pitch_control import PlayerSnapshot, pitch_control_surface

# 4-3-3 attacking side, 4-4-2 defending side. Each attacker is a named
# "player" in the cohort so the leaderboard shows recognisable rows.
ATTACK_LINEUP: tuple[tuple[str, str, float, float], ...] = (
    ("A01", "GK", 8.0, 34.0),
    ("A02", "CB", 25.0, 24.0),
    ("A03", "CB", 25.0, 44.0),
    ("A04", "FB", 30.0, 8.0),
    ("A05", "FB", 30.0, 60.0),
    ("A06", "DM", 45.0, 34.0),
    ("A07", "CM", 55.0, 22.0),
    ("A08", "CM", 55.0, 46.0),
    ("A09", "WG", 75.0, 10.0),
    ("A10", "ST", 82.0, 34.0),
    ("A11", "WG", 75.0, 58.0),
)

DEFENCE_LINEUP: tuple[tuple[str, str, float, float], ...] = (
    ("D01", "GK", 98.0, 34.0),
    ("D02", "CB", 78.0, 26.0),
    ("D03", "CB", 78.0, 42.0),
    ("D04", "FB", 75.0, 10.0),
    ("D05", "FB", 75.0, 58.0),
    ("D06", "DM", 60.0, 20.0),
    ("D07", "DM", 60.0, 48.0),
    ("D08", "CM", 55.0, 28.0),
    ("D09", "CM", 55.0, 40.0),
    ("D10", "ST", 40.0, 24.0),
    ("D11", "ST", 40.0, 44.0),
)

# How much each position is weighted when picking the "mover" in a
# simulated action. Forwards and wide players move into high-xT zones
# more often than centre-backs and goalkeepers.
POSITION_MOVER_WEIGHT: dict[str, float] = {
    "GK": 0.0,
    "CB": 0.2,
    "FB": 0.8,
    "DM": 0.5,
    "CM": 1.0,
    "AM": 1.4,
    "WG": 1.6,
    "ST": 1.8,
}


@dataclass(frozen=True, slots=True)
class AttackerProfile:
    player_id: str
    name: str
    position: str
    base_x: float
    base_y: float


@dataclass(frozen=True, slots=True)
class PlayerDDI:
    player_id: str
    name: str
    position: str
    ddi_m2: float
    actions: int
    avg_per_action: float


@dataclass(frozen=True, slots=True)
class MatchDDI:
    seed: int
    n_actions: int
    tau: float
    total_ddi_m2: float
    leaderboard: tuple[PlayerDDI, ...]


def _build_name(position: str, idx: int) -> str:
    # Deterministic placeholder names so the UI shows something human-ish.
    first = (
        "Ahmed",
        "Mohamed",
        "Karim",
        "Yassine",
        "Omar",
        "Salah",
        "Ibrahim",
        "Hassan",
        "Tarek",
        "Sofiane",
        "Amine",
    )
    last = (
        "Hassan",
        "Mahmoud",
        "Benali",
        "El-Sharif",
        "Riad",
        "Al-Shami",
        "Boulaid",
        "Haddad",
        "Farouk",
        "Bennacer",
        "Ziyech",
    )
    return f"{first[idx % len(first)]} {last[(idx * 3 + 1) % len(last)]} ({position})"


def build_attack_squad() -> tuple[AttackerProfile, ...]:
    return tuple(
        AttackerProfile(
            player_id=pid,
            name=_build_name(pos, i),
            position=pos,
            base_x=x,
            base_y=y,
        )
        for i, (pid, pos, x, y) in enumerate(ATTACK_LINEUP)
    )


def _base_snapshots(
    attack: tuple[AttackerProfile, ...],
) -> list[PlayerSnapshot]:
    players: list[PlayerSnapshot] = []
    for a in attack:
        players.append(PlayerSnapshot(x=a.base_x, y=a.base_y, team=0))
    for _, _, dx, dy in DEFENCE_LINEUP:
        players.append(PlayerSnapshot(x=dx, y=dy, team=1))
    return players


def _shift_for(position: str, rng: np.random.Generator) -> tuple[float, float]:
    """How far the mover steps forward into the final third.

    Lines that already live high (WG/ST) get smaller shifts; deeper lines
    get larger shifts to reach the high-xT zone.
    """
    base_dx = {
        "GK": 0.0,
        "CB": 10.0,
        "FB": 11.0,
        "DM": 10.0,
        "CM": 10.0,
        "AM": 9.0,
        "WG": 8.0,
        "ST": 6.0,
    }.get(position, 8.0)
    dx = base_dx + rng.normal(0.0, 1.2)
    dy = rng.normal(0.0, 2.0)
    return float(dx), float(dy)


def _pick_mover(
    attack: tuple[AttackerProfile, ...],
    rng: np.random.Generator,
) -> int:
    weights = np.array(
        [POSITION_MOVER_WEIGHT.get(a.position, 0.0) for a in attack],
        dtype=np.float64,
    )
    total = weights.sum()
    if total <= 0.0:
        return int(rng.integers(0, len(attack)))
    probs = weights / total
    return int(rng.choice(len(attack), p=probs))


def simulate_match_ddi(
    seed: int = 0,
    n_actions: int = 60,
    tau: float = DEFAULT_TAU,
    grid_shape: tuple[int, int] = (20, 30),
) -> MatchDDI:
    """Run ``n_actions`` off-ball actions and aggregate per-attacker DDI.

    Parameters
    ----------
    seed : int
        Master RNG seed. Makes the whole match deterministic.
    n_actions : int
        Number of single-mover actions to simulate.
    tau : float
        High-xT threshold (paper default 0.08).
    grid_shape : tuple[int, int]
        Pitch-control grid resolution. (20, 30) is fast enough for interactive
        dashboards and still resolves the penalty-box region well.
    """
    if n_actions <= 0:
        raise ValueError("n_actions must be positive")
    if grid_shape[0] < 4 or grid_shape[1] < 4:
        raise ValueError("grid must be at least 4x4 for DDI integration")

    rng = np.random.default_rng(seed)
    attack = build_attack_squad()
    base = _base_snapshots(attack)
    n_attack = len(attack)

    # Precompute Phi_before once — the baseline never changes because the
    # only thing that differs between actions is which attacker moves.
    phi_before, xx, yy = pitch_control_surface(base, grid_shape=grid_shape)

    totals = np.zeros(n_attack, dtype=np.float64)
    counts = np.zeros(n_attack, dtype=np.int64)

    for _ in range(n_actions):
        j = _pick_mover(attack, rng)
        if POSITION_MOVER_WEIGHT.get(attack[j].position, 0.0) == 0.0:
            continue
        dx, dy = _shift_for(attack[j].position, rng)
        # Build the "after" snapshot — copy base, shift attacker j.
        after: list[PlayerSnapshot] = list(base)
        mover = after[j]
        after[j] = PlayerSnapshot(
            x=float(np.clip(mover.x + dx, 0.0, 105.0)),
            y=float(np.clip(mover.y + dy, 0.0, 68.0)),
            vx=mover.vx,
            vy=mover.vy,
            team=mover.team,
        )
        phi_after, _, _ = pitch_control_surface(after, grid_shape=grid_shape)
        val = ddi(phi_before, phi_after, xx, yy, tau=tau)
        totals[j] += float(val)
        counts[j] += 1

    leaderboard = tuple(
        PlayerDDI(
            player_id=a.player_id,
            name=a.name,
            position=a.position,
            ddi_m2=float(totals[i]),
            actions=int(counts[i]),
            avg_per_action=float(totals[i] / counts[i]) if counts[i] else 0.0,
        )
        for i, a in enumerate(attack)
    )
    leaderboard = tuple(sorted(leaderboard, key=lambda p: p.ddi_m2, reverse=True))

    return MatchDDI(
        seed=seed,
        n_actions=n_actions,
        tau=tau,
        total_ddi_m2=float(totals.sum()),
        leaderboard=leaderboard,
    )

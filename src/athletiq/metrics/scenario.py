"""Tactical Counterfactual Lab — scenario-level helpers around Pitch Control.

Given raw player positions (not stochastic events) we compute:

* ``phi_from_positions(...)`` — a thin wrapper around
  :func:`athletiq.metrics.pitch_control.pitch_control_surface` that takes raw
  ``(x, y)`` arrays for attackers, defenders, and the ball, plus optional
  velocities, and returns the 2-D :math:`\\Phi` surface + 1-D axis grids.
* ``defensive_line_height_m(...)`` — the mean ``x`` of the N deepest defenders
  (standard tactical proxy for "how high did we press?").
* ``FORMATION_PRESETS`` — 4-4-2 / 4-3-3 / 3-5-2 / 5-4-1 attacker **and**
  defender templates, expressed as ``(x, y)`` tuples on the canonical
  105 x 68 m pitch. The Lab seeds a scenario from any preset.
* ``diff_scenarios(...)`` — compares two Pitch Control outputs and returns a
  :class:`ScenarioDiff` with area-averaged / zonal / defensive-line deltas
  plus a plain-English coach headline.

All functions are deterministic, grid-independent, and do not touch the
network. They are designed to be fast enough for interactive drag UX
(<100 ms for a 34 x 52 grid on a laptop-grade CPU).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import numpy.typing as npt

from athletiq.metrics.pitch_control import PlayerSnapshot, pitch_control_surface
from athletiq.metrics.pitch_control_zones import (
    THIRD_NAMES,
    ZonalSummary,
)
from athletiq.metrics.types import PITCH_LENGTH_M, PITCH_WIDTH_M

FloatArray = npt.NDArray[np.floating]

# ---------------------------------------------------------------------------
# phi_from_positions
# ---------------------------------------------------------------------------


def phi_from_positions(
    attackers: FloatArray | list[tuple[float, float]],
    defenders: FloatArray | list[tuple[float, float]],
    ball: tuple[float, float] | FloatArray,
    *,
    attacker_velocities: FloatArray | None = None,
    defender_velocities: FloatArray | None = None,
    grid_shape: tuple[int, int] = (34, 52),
    pitch_length: float = PITCH_LENGTH_M,
    pitch_width: float = PITCH_WIDTH_M,
) -> tuple[FloatArray, FloatArray, FloatArray]:
    """Compute :math:`\\Phi` directly from raw player positions.

    Parameters
    ----------
    attackers, defenders : (N, 2) arrays or list of (x, y) tuples
        Positions of attackers and defenders, in pitch-metric coordinates.
    ball : (2,) — ball position.
        Included for API symmetry (the TTI surface doesn't use the ball
        location directly; downstream xG / carry heads in PR 5 will).
    attacker_velocities, defender_velocities : optional (N, 2) arrays
        Player velocities (m/s). Defaults to zero (static snapshot).
    grid_shape : (rows, cols)
        Output grid resolution. Default 34x52 matches ``/api/pitch-control/demo``.
    pitch_length, pitch_width : float
        Physical pitch dimensions.

    Returns
    -------
    phi : (rows, cols) float array — attacker dominance probability in [0, 1].
    xs, ys : 1-D axes in metres (column-centres along x, row-centres along y).
    """
    atk = _as_positions(attackers, name="attackers")
    dfn = _as_positions(defenders, name="defenders")
    _ = np.asarray(ball, dtype=np.float64).reshape(2)  # validate ball shape

    atk_vel = _as_velocities(attacker_velocities, n=atk.shape[0], name="attackers")
    dfn_vel = _as_velocities(defender_velocities, n=dfn.shape[0], name="defenders")

    players: list[PlayerSnapshot] = []
    for (x, y), (vx, vy) in zip(atk, atk_vel, strict=True):
        players.append(PlayerSnapshot(x=float(x), y=float(y), vx=float(vx), vy=float(vy), team=0))
    for (x, y), (vx, vy) in zip(dfn, dfn_vel, strict=True):
        players.append(PlayerSnapshot(x=float(x), y=float(y), vx=float(vx), vy=float(vy), team=1))

    phi, xx, yy = pitch_control_surface(
        players,
        grid_shape=grid_shape,
        pitch_length=pitch_length,
        pitch_width=pitch_width,
    )
    return phi, xx[0], yy[:, 0]


def _as_positions(xy: FloatArray | list[tuple[float, float]], *, name: str) -> FloatArray:
    arr = np.asarray(xy, dtype=np.float64)
    if arr.ndim != 2 or arr.shape[1] != 2:
        raise ValueError(f"{name} must be shape (N, 2), got {arr.shape}")
    if arr.shape[0] < 1:
        raise ValueError(f"{name} must have at least 1 position")
    return arr


def _as_velocities(
    vel: FloatArray | None,
    *,
    n: int,
    name: str,
) -> FloatArray:
    if vel is None:
        return np.zeros((n, 2), dtype=np.float64)
    arr = np.asarray(vel, dtype=np.float64)
    if arr.shape != (n, 2):
        raise ValueError(f"{name} velocities must be shape ({n}, 2), got {arr.shape}")
    return arr


# ---------------------------------------------------------------------------
# defensive line height
# ---------------------------------------------------------------------------

AttackingDirection = Literal["+x", "-x"]


def defensive_line_height_m(
    defenders: FloatArray | list[tuple[float, float]],
    *,
    attacking_direction: AttackingDirection = "+x",
    n_back: int = 4,
) -> float:
    """How far up the pitch the defender's back line sits, in metres.

    Convention — ``attacking_direction="+x"`` (our repo default) means the
    attacker attacks toward higher ``x`` and the defender's own goal line is
    at ``x = PITCH_LENGTH_M``. The DEFENDER's GK therefore has the largest
    ``x`` and the back line has the next-largest ``x`` values.

    The returned value is the distance from the defender's own goal line to
    the mean ``x`` of the back line (after excluding the GK). Higher value
    means the defence is pushed FURTHER UP THE PITCH (pressing high); lower
    value means it has dropped into a deep block.

    Parameters
    ----------
    defenders : list/array of (x, y) — all 11 defenders including GK.
    attacking_direction : ``"+x"`` or ``"-x"`` — direction the ATTACKER
        is attacking. Values are mirrored internally when ``"-x"``.
    n_back : int — size of the back line (default 4). We average ``n_back``
        defenders after dropping the goalkeeper.

    Returns
    -------
    line_height_m : float — distance from the defender's own goal to their
        back line, in metres; always in ``[0, PITCH_LENGTH_M]``.
    """
    arr = _as_positions(defenders, name="defenders")
    xs = arr[:, 0].astype(np.float64)
    if attacking_direction == "-x":
        xs = PITCH_LENGTH_M - xs
    # Defender's own goal is at x = PITCH_LENGTH_M. Largest x = GK; next-
    # largest = back line. Line height = PITCH_LENGTH_M - mean(back line x).
    order = np.argsort(xs)[::-1]  # descending: largest x first
    if len(order) <= n_back:
        return float(PITCH_LENGTH_M - xs.mean())
    back_line_idx = order[1 : 1 + n_back]
    return float(PITCH_LENGTH_M - xs[back_line_idx].mean())


# ---------------------------------------------------------------------------
# formation presets
# ---------------------------------------------------------------------------


def _preset_attacker(formation: str) -> list[tuple[float, float]]:
    """Attacker template (attacking toward +x), GK at low x."""
    presets: dict[str, list[tuple[float, float]]] = {
        "4-4-2": [
            (10, 34),  # GK
            (30, 12),
            (30, 26),
            (30, 42),
            (30, 56),  # back 4
            (55, 12),
            (55, 26),
            (55, 42),
            (55, 56),  # mid 4
            (85, 26),
            (85, 42),  # front 2
        ],
        "4-3-3": [
            (10, 34),
            (30, 12),
            (30, 26),
            (30, 42),
            (30, 56),
            (55, 20),
            (55, 34),
            (55, 48),
            (82, 12),
            (88, 34),
            (82, 56),
        ],
        "3-5-2": [
            (10, 34),
            (30, 20),
            (30, 34),
            (30, 48),
            (55, 8),
            (55, 22),
            (55, 34),
            (55, 46),
            (55, 60),
            (85, 26),
            (85, 42),
        ],
        "5-4-1": [
            (10, 34),
            (30, 8),
            (30, 22),
            (30, 34),
            (30, 46),
            (30, 60),
            (55, 14),
            (55, 28),
            (55, 40),
            (55, 54),
            (85, 34),
        ],
    }
    if formation not in presets:
        raise ValueError(f"Unknown formation '{formation}'. Valid: {sorted(presets)}")
    return presets[formation]


def _mirror_defender(attacker_template: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Mirror an attacker template across the halfway line for the defender."""
    return [(PITCH_LENGTH_M - x, y) for (x, y) in attacker_template]


VALID_FORMATIONS: tuple[str, ...] = ("4-4-2", "4-3-3", "3-5-2", "5-4-1")


def formation_preset(
    formation: str,
    role: Literal["attacker", "defender"],
) -> list[tuple[float, float]]:
    """Return the 11 (x, y) template positions for a role + formation.

    The attacker template attacks toward +x (GK at low x, forwards at high x).
    The defender template is the mirror image (GK at high x, back line on the
    attacker's side) — so placing attackers + defenders with the same
    formation yields a realistic 11v11 starting position.
    """
    if role == "attacker":
        return list(_preset_attacker(formation))
    if role == "defender":
        return _mirror_defender(_preset_attacker(formation))
    raise ValueError(f"role must be 'attacker' or 'defender', got {role!r}")


def default_ball_position() -> tuple[float, float]:
    """Centre spot."""
    return (PITCH_LENGTH_M / 2.0, PITCH_WIDTH_M / 2.0)


# ---------------------------------------------------------------------------
# scenario diff
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ScenarioDiff:
    """Numerical delta between a baseline scenario and an edited one.

    All ``delta_*`` values are ``scenario - baseline``. Positive values mean
    the scenario moved *toward* the attacker (more Φ, higher line, more
    final-third dominance, more territorial balance for the attacker).
    """

    delta_phi_mean: float
    """Whole-pitch mean attacker dominance delta (scenario - baseline)."""

    delta_phi_final_third: float
    """Mean attacker dominance delta restricted to the attacking third."""

    delta_balance_attacker_pct: float
    """Territorial balance delta, in percentage points (attacker side)."""

    delta_defensive_line_height_m: float
    """How much further up the pitch the DEFENDER pushed their back line
    (positive = defender pressed higher; negative = dropped deeper)."""

    per_zone_delta: list[float]
    """12 zone mean-Φ deltas (4 channels x 3 thirds), row-major, channel-first."""

    headline: str
    """Plain-English one-line coach verdict describing the biggest change
    plus a net judgement (win / trade-off / loss for the attacker)."""


def diff_scenarios(
    *,
    baseline: ZonalSummary,
    scenario: ZonalSummary,
    baseline_phi: FloatArray,
    scenario_phi: FloatArray,
    baseline_xs: FloatArray,
    scenario_xs: FloatArray,
    baseline_defenders: FloatArray | list[tuple[float, float]],
    scenario_defenders: FloatArray | list[tuple[float, float]],
    attacking_direction: AttackingDirection = "+x",
) -> ScenarioDiff:
    """Compute the coach-facing delta between two scenarios.

    Both scenarios must share the same grid shape and axes so that zonal
    deltas line up cell-for-cell. Ball position is not used here; xG deltas
    land in PR 5.
    """
    if baseline_phi.shape != scenario_phi.shape:
        raise ValueError(
            "baseline and scenario must share grid shape; "
            f"got {baseline_phi.shape} vs {scenario_phi.shape}"
        )
    if not np.allclose(baseline_xs, scenario_xs):
        raise ValueError("baseline and scenario must share the x-axis grid")
    if len(baseline.zones) != len(scenario.zones):
        raise ValueError(
            "baseline and scenario zone count mismatch "
            f"({len(baseline.zones)} vs {len(scenario.zones)})"
        )

    delta_mean = float(scenario_phi.mean() - baseline_phi.mean())

    # final-third average using the column index range of the attacking third.
    # Zonal summary already has the range; we recompute mean from the raw grid
    # using the x-axis to stay grid-independent.
    final_third_mask = _final_third_mask(scenario_xs)
    delta_final_third = float(
        scenario_phi[:, final_third_mask].mean() - baseline_phi[:, final_third_mask].mean()
    )

    delta_balance = float(scenario.balance_attacker_pct - baseline.balance_attacker_pct)

    baseline_line = defensive_line_height_m(
        baseline_defenders, attacking_direction=attacking_direction
    )
    scenario_line = defensive_line_height_m(
        scenario_defenders, attacking_direction=attacking_direction
    )
    delta_line = float(scenario_line - baseline_line)

    per_zone_delta = [
        float(s.phi_mean - b.phi_mean) for b, s in zip(baseline.zones, scenario.zones, strict=True)
    ]

    headline = _scenario_headline(
        delta_phi_mean=delta_mean,
        delta_phi_final_third=delta_final_third,
        delta_balance=delta_balance,
        delta_line=delta_line,
        baseline=baseline,
        scenario=scenario,
    )

    return ScenarioDiff(
        delta_phi_mean=delta_mean,
        delta_phi_final_third=delta_final_third,
        delta_balance_attacker_pct=delta_balance,
        delta_defensive_line_height_m=delta_line,
        per_zone_delta=per_zone_delta,
        headline=headline,
    )


def _final_third_mask(xs: FloatArray) -> FloatArray:
    """Boolean mask selecting columns in the attacker's final (attacking) third."""
    xs_1d = np.asarray(xs)
    if xs_1d.ndim > 1:
        xs_1d = xs_1d[0]
    threshold = (2.0 / 3.0) * PITCH_LENGTH_M
    return xs_1d >= threshold


def _scenario_headline(
    *,
    delta_phi_mean: float,
    delta_phi_final_third: float,
    delta_balance: float,
    delta_line: float,
    baseline: ZonalSummary,
    scenario: ZonalSummary,
) -> str:
    """Deterministic two-sentence coach verdict.

    Sentence 1 names the biggest tactical change (line height / final-third
    dominance / hottest zone). Sentence 2 gives the net judgement from the
    attacker's perspective.
    """
    eps = 0.005

    # Pick the headline lever: defensive-line change if it moved by >= 1 m,
    # else final-third Φ change, else hottest-attacking-zone change.
    if abs(delta_line) >= 1.0:
        direction = "pushed up" if delta_line > 0 else "dropped back"
        lever = (
            f"Defensive line {direction} {abs(delta_line):.1f} m "
            f"(final-third Φ Δ{delta_phi_final_third:+.2f})."
        )
    elif abs(delta_phi_final_third) >= 0.01:
        lever = (
            f"Final-third Φ moved {delta_phi_final_third:+.2f} "
            f"(whole-pitch Δ{delta_phi_mean:+.2f})."
        )
    elif baseline.hottest_attack.label != scenario.hottest_attack.label:
        lever = (
            f"Most dangerous attacking zone shifted — "
            f"{baseline.hottest_attack.label.lower()} (Φ={baseline.hottest_attack.phi_mean:.2f}) "
            f"→ {scenario.hottest_attack.label.lower()} "
            f"(Φ={scenario.hottest_attack.phi_mean:.2f})."
        )
    else:
        lever = "Scenario is within noise — Φ unchanged at the pitch level."

    # Net judgement: look at the combined signal on the attacker side.
    # A positive signal for the attacker = more Φ everywhere + more in final
    # third + no catastrophic mid-block exposure.
    attacker_signal = delta_phi_mean + delta_phi_final_third + 0.01 * delta_balance
    if abs(attacker_signal) < eps:
        verdict = "Net effect is within noise for both sides."
    elif attacker_signal > 0 and delta_phi_final_third > 0:
        verdict = "Attack gained ground without giving up structure."
    elif attacker_signal < 0 and delta_phi_final_third < 0:
        verdict = "Attack lost ground — defence tightened the final third."
    elif delta_phi_final_third > 0 >= delta_phi_mean:
        verdict = "Trade-off: sharper in the final third but exposed elsewhere."
    elif delta_phi_final_third < 0 <= delta_phi_mean:
        verdict = "Trade-off: more territory overall but less bite at goal."
    else:
        verdict = "Mixed signal — check the zone deltas for detail."

    return f"{lever} {verdict}"


__all__ = [
    "FORMATION_THIRDS",
    "ScenarioDiff",
    "VALID_FORMATIONS",
    "default_ball_position",
    "defensive_line_height_m",
    "diff_scenarios",
    "formation_preset",
    "phi_from_positions",
]

# exposed for /api/pitch-control/scenario/preset — tells the UI what
# third-name strings to render on the zonal axes so they stay in sync with
# :mod:`pitch_control_zones`.
FORMATION_THIRDS = THIRD_NAMES

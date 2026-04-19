"""Scenario-level Expected Goals (xG) surface.

The Counterfactual Lab needs an answer to: "given this arrangement of
attackers / defenders / ball, how much attacking threat does each team
carry?" That's a different question from classic event-level xG (which
takes a real shot's (x, y) + body part + assist type) because there is
no shot yet — only a static pitch-control surface.

We solve it with an **Expected Threat surface** in the spirit of Karun
Singh's xT (2019). For each cell of the Pitch Control grid we ask:

  - If the attacker owns this cell (Φ), how likely is a shot taken
    *from here* to become a goal? That's a classical geometric xG prior
    computed from (distance, angle to goal).
  - Inverse for the defender: (1 - Φ) weighted, mirrored goal.

Integrated over the pitch this gives two scalars — ``xg_for`` and
``xg_against`` — whose difference is a compact "net attacking value"
for the scenario. The Lab diff cards surface baseline → current → Δ.

This is intentionally a *lightweight* xG:

* No body-part prior (all shots treated as right foot / head-neutral).
* No assist prior (we weight by Φ instead, which plays the same role of
  "did we have control long enough to shoot?").
* No defender density beyond Φ's own TTI-based geometry — Φ already
  encodes pressure, so we don't double-count by adding a separate
  pressure term.

Coefficients are calibrated from a StatsBomb open-data logistic fit
used in the wider VAEP-lite head: ``sigmoid(-0.054 * distance +
1.180 * angle_rad - 0.739)``. The same prior is reused here so the
``/metrics`` event-level xG and the ``/lab`` scenario xG speak the
same language.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from athletiq.metrics.types import PITCH_LENGTH_M, PITCH_WIDTH_M

FloatArray = npt.NDArray[np.floating]

# Geometric xG logistic coefficients (distance_m, angle_rad, bias).
# Hand-tuned against a small set of coach-intuition anchors:
#   - penalty spot (11 m central):       ~0.61
#   - 6-yard box central (5 m):          ~0.78
#   - 18-yard edge central (16.5 m):     ~0.35
#   - 30 m central:                      ~0.07
# The absolute levels are optimistic vs. shot-outcome averages because a
# geometric-only prior can't see keeper / defender pressure directly — but
# the *ordering* matches coach intuition and that's what the Lab needs.
_XG_B_DIST = -0.120
_XG_B_ANGLE = 2.000
_XG_B_BIAS = 0.500

# Goal mouth width in metres (FIFA standard 7.32 m).
_GOAL_WIDTH = 7.32


@dataclass(frozen=True, slots=True)
class ScenarioXG:
    """Scenario-level attacker/defender expected-goal scalars.

    ``xg_for`` and ``xg_against`` are dimensionless expected-threat
    integrals over the pitch, normalised so that a balanced mid-press
    formation sits near ``xg_for ≈ xg_against ≈ 0.05``. They are not
    calibrated to "goals per possession" — treat them as a relative
    ranking signal for comparing two scenarios.
    """

    xg_for: float
    """Attacker expected-threat scalar (higher = more dangerous)."""

    xg_against: float
    """Defender expected-threat scalar (higher = more exposure in transition)."""

    xg_net: float
    """``xg_for - xg_against`` — net attacking edge."""


def _goal_centres(attacking_direction: str) -> tuple[tuple[float, float], tuple[float, float]]:
    """Return (attacker_target_goal, defender_target_goal) centres."""
    if attacking_direction not in ("+x", "-x"):
        raise ValueError(f"attacking_direction must be '+x' or '-x', got {attacking_direction!r}")
    if attacking_direction == "+x":
        atk_goal = (PITCH_LENGTH_M, PITCH_WIDTH_M / 2.0)
        def_goal = (0.0, PITCH_WIDTH_M / 2.0)
    else:
        atk_goal = (0.0, PITCH_WIDTH_M / 2.0)
        def_goal = (PITCH_LENGTH_M, PITCH_WIDTH_M / 2.0)
    return atk_goal, def_goal


def geometric_xg(
    x: float | FloatArray,
    y: float | FloatArray,
    *,
    goal: tuple[float, float] | None = None,
    attacking_direction: str = "+x",
) -> FloatArray:
    """Geometric xG prior — probability a shot from (x, y) becomes a goal.

    Uses distance-to-goal and the angle subtended by the goal mouth, via a
    logistic of the form ``sigmoid(b_dist * d + b_angle * a + bias)``.

    Parameters
    ----------
    x, y : scalar or array of metre-space coordinates.
    goal : optional ``(gx, gy)`` goal centre override. Defaults from
        ``attacking_direction``.
    attacking_direction : ``"+x"`` (attack right goal) or ``"-x"`` (attack
        left goal). Ignored when ``goal`` is explicit.

    Returns
    -------
    ndarray of the same shape as ``x``, values in (0, 1).
    """
    if goal is None:
        atk_goal, _ = _goal_centres(attacking_direction)
        goal = atk_goal
    gx, gy = goal
    x_arr = np.asarray(x, dtype=np.float64)
    y_arr = np.asarray(y, dtype=np.float64)

    # Straight-line distance to goal centre (m).
    distance = np.sqrt((gx - x_arr) ** 2 + (gy - y_arr) ** 2)
    # Guard the angle computation: below 0.5 m from the centre the formula
    # diverges; clamp to 0.5 m so the logistic stays well-defined.
    distance = np.maximum(distance, 0.5)

    # Angle subtended by the goal mouth at (x, y). Cosine-rule form so it
    # holds for off-centre shots too. See Caley (2013) for the derivation.
    half = _GOAL_WIDTH / 2.0
    # Vectors to the two posts.
    dx1 = gx - x_arr
    dy1 = (gy - half) - y_arr
    dx2 = gx - x_arr
    dy2 = (gy + half) - y_arr
    dot = dx1 * dx2 + dy1 * dy2
    n1 = np.sqrt(dx1 * dx1 + dy1 * dy1)
    n2 = np.sqrt(dx2 * dx2 + dy2 * dy2)
    cos_a = np.clip(dot / np.maximum(n1 * n2, 1e-9), -1.0, 1.0)
    angle = np.arccos(cos_a)  # radians, [0, pi]

    z = _XG_B_DIST * distance + _XG_B_ANGLE * angle + _XG_B_BIAS
    return 1.0 / (1.0 + np.exp(-z))


_DEFAULT_BALL_SIGMA_M = 22.0
"""Gaussian half-width (m) used to weight cells by reachable-from-ball distance.

22 m covers a realistic ~3–5 s ball trajectory at pass speed. Cells far from
the ball receive near-zero weight — without this kernel a static snapshot
looks symmetric (both teams "own" their half) and the xG scalars can't tell
which side actually benefits from current ball position.
"""


def xg_surface(
    phi: FloatArray,
    xs: FloatArray,
    ys: FloatArray,
    *,
    attacking_direction: str = "+x",
) -> tuple[FloatArray, FloatArray]:
    """Per-cell expected-threat grids for attacker and defender.

    Returns ``(xg_for_cell, xg_against_cell)`` — both ``phi.shape`` — where
    each cell is the geometric xG prior at that location multiplied by the
    appropriate pitch-control weight (Φ for attacker, 1-Φ for defender).
    """
    phi_arr = np.asarray(phi, dtype=np.float64)
    xs_1d = np.asarray(xs, dtype=np.float64).reshape(-1)
    ys_1d = np.asarray(ys, dtype=np.float64).reshape(-1)
    if phi_arr.shape != (ys_1d.size, xs_1d.size):
        raise ValueError(
            f"phi shape {phi_arr.shape} does not match (len(ys), len(xs))="
            f"({ys_1d.size}, {xs_1d.size})"
        )

    xx, yy = np.meshgrid(xs_1d, ys_1d)
    atk_goal, def_goal = _goal_centres(attacking_direction)

    xg_atk_map = geometric_xg(xx, yy, goal=atk_goal)
    xg_def_map = geometric_xg(xx, yy, goal=def_goal)

    xg_for_cell = xg_atk_map * phi_arr
    xg_against_cell = xg_def_map * (1.0 - phi_arr)
    return xg_for_cell, xg_against_cell


def _ball_kernel(
    xs: FloatArray,
    ys: FloatArray,
    ball: tuple[float, float] | None,
    sigma_m: float,
) -> FloatArray:
    """2-D Gaussian over the pitch centred on ``ball`` with width ``sigma_m``.

    When ``ball`` is None returns a uniform kernel (recovering a raw mean).
    """
    xs_1d = np.asarray(xs, dtype=np.float64).reshape(-1)
    ys_1d = np.asarray(ys, dtype=np.float64).reshape(-1)
    xx, yy = np.meshgrid(xs_1d, ys_1d)
    if ball is None:
        return np.ones_like(xx)
    bx, by = ball
    d2 = (xx - bx) ** 2 + (yy - by) ** 2
    return np.exp(-d2 / (2.0 * sigma_m**2))


def scenario_xg(
    phi: FloatArray,
    xs: FloatArray,
    ys: FloatArray,
    *,
    ball: tuple[float, float] | None = None,
    attacking_direction: str = "+x",
    ball_sigma_m: float = _DEFAULT_BALL_SIGMA_M,
) -> ScenarioXG:
    """Reduce a pitch-control surface to attacker/defender xG scalars.

    Each cell's attacker / defender expected-threat from :func:`xg_surface`
    is weighted by a Gaussian kernel centred on the ball (width
    ``ball_sigma_m`` metres, default 22 m). Without this kernel a static
    snapshot is symmetric — both teams automatically "own" their own half,
    including the high-xG zones on their opponent's side — so the naive
    mean can't tell which side actually benefits from where the ball is.

    When ``ball`` is None the kernel is uniform (raw mean). Useful for
    diagnostic unit tests of the underlying grid.
    """
    for_cell, against_cell = xg_surface(phi, xs, ys, attacking_direction=attacking_direction)
    kernel = _ball_kernel(xs, ys, ball, ball_sigma_m)
    denom = float(kernel.sum())
    if denom <= 0.0:
        xg_for = float(for_cell.mean())
        xg_against = float(against_cell.mean())
    else:
        xg_for = float((for_cell * kernel).sum() / denom)
        xg_against = float((against_cell * kernel).sum() / denom)
    return ScenarioXG(
        xg_for=xg_for,
        xg_against=xg_against,
        xg_net=xg_for - xg_against,
    )

"""Pitch Control surface (paper §3.4.1, Eq. 7).

We implement a time-to-intercept (TTI) based pitch-control surface in the
spirit of Spearman (2018): at each pitch point ``x``, each player's time to
reach ``x`` is predicted as ``(||x - p|| - r_reach) / v_max`` (clamped at 0),
then an attacking-vs-defending logistic mixture yields the probability
``Phi(x)`` that the attacking team can control the ball at ``x``.

This is a prototype-grade implementation: vectorised over a grid, fast enough
for interactive dashboards, but without stochastic arrival-time modelling.
Upgrade to Spearman's full probabilistic model is a v2 seam.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from athletiq.metrics.types import PITCH_LENGTH_M, PITCH_WIDTH_M

FloatArray = npt.NDArray[np.floating]


@dataclass(frozen=True, slots=True)
class PlayerSnapshot:
    """Instantaneous state of a player for pitch-control modelling."""

    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    team: int = 0  # 0 = attacking, 1 = defending

    @property
    def position(self) -> tuple[float, float]:
        return self.x, self.y


def _tti(
    positions: FloatArray,
    velocities: FloatArray,
    grid_xy: FloatArray,
    v_max: float,
    reaction_s: float,
) -> FloatArray:
    """Time-to-intercept for each player at every grid point.

    Shapes:
        positions  : (P, 2)
        velocities : (P, 2)
        grid_xy    : (H, W, 2)
    Returns (P, H, W).
    """
    # predicted position after reaction delay
    predicted = positions + velocities * reaction_s  # (P, 2)
    # broadcast to (P, H, W, 2) then L2
    diff = grid_xy[None, :, :, :] - predicted[:, None, None, :]
    dist = np.linalg.norm(diff, axis=-1)  # (P, H, W)
    return np.clip(dist / v_max, a_min=0.0, a_max=None)


def pitch_control_surface(
    players: list[PlayerSnapshot],
    grid_shape: tuple[int, int] = (68, 105),
    pitch_length: float = PITCH_LENGTH_M,
    pitch_width: float = PITCH_WIDTH_M,
    v_max: float = 7.0,
    reaction_s: float = 0.7,
    steepness: float = 1.5,
) -> tuple[FloatArray, FloatArray, FloatArray]:
    """Eq. 7 — attacking-team pitch control Phi(x) on a regular grid.

    Parameters
    ----------
    players : list[PlayerSnapshot]
        All 22 (or fewer) players currently on the pitch.
    grid_shape : (H, W)
        Grid resolution (rows, cols). Default (68, 105) == 1 m resolution.
    pitch_length, pitch_width : float
        Pitch dimensions in metres.
    v_max : float
        Max player closing speed (m/s).
    reaction_s : float
        Reaction-time delay before max-speed movement.
    steepness : float
        Logistic sharpness for the TTI difference.

    Returns
    -------
    Phi : (H, W) array, probability that the attacking team controls the point.
    xx  : (H, W) array of x-coordinates.
    yy  : (H, W) array of y-coordinates.
    """
    if not players:
        raise ValueError("players must be non-empty")

    H, W = grid_shape
    xs = np.linspace(0.5, pitch_length - 0.5, W)
    ys = np.linspace(0.5, pitch_width - 0.5, H)
    xx, yy = np.meshgrid(xs, ys)
    grid_xy = np.stack([xx, yy], axis=-1)  # (H, W, 2)

    positions = np.array([[p.x, p.y] for p in players], dtype=np.float64)
    velocities = np.array([[p.vx, p.vy] for p in players], dtype=np.float64)
    teams = np.array([p.team for p in players], dtype=np.int64)

    tti = _tti(positions, velocities, grid_xy, v_max=v_max, reaction_s=reaction_s)

    # min TTI per team
    atk_mask = teams == 0
    def_mask = teams == 1
    if not atk_mask.any() or not def_mask.any():
        raise ValueError("need at least one attacker and one defender")
    atk_min = tti[atk_mask].min(axis=0)
    def_min = tti[def_mask].min(axis=0)

    # logistic: attacker faster => Phi -> 1, defender faster => Phi -> 0
    phi = 1.0 / (1.0 + np.exp(steepness * (atk_min - def_min)))
    return phi, xx, yy

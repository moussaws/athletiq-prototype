"""Pressure field (AthletIQ paper §3.1).

Reference equations:

    P^r_{a,b} = (r - d_{a,b})^2        if 0 <= d_{a,b} <= r   (Eq. 1)
    P^r_{a,b} = 0                      otherwise

    p^r_{a,b} = P^r_{a,b} / (pi * r^2)                         (Eq. 2)

    P^r_{A,l} = sum_{a in A} p^r_{a,b}                         (Eq. 3)

    mean_P^r_{A,l} = (1 / |F|) * sum_{f in F} P^r_{A,l}(f)     (Eq. 4)

All distances are in metres. Positions are 2-D NumPy arrays with shape
``(n, 2)``; single-position arguments accept shape ``(2,)`` and are
broadcast.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
import numpy.typing as npt

ArrayLike = npt.ArrayLike
FloatArray = npt.NDArray[np.floating]

DEFAULT_INFLUENCE_RADIUS_M: float = 5.0
"""Default effective influence radius r, as suggested by the paper (§3.1)."""


def _as_2d(points: ArrayLike) -> FloatArray:
    arr = np.asarray(points, dtype=np.float64)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    if arr.ndim != 2 or arr.shape[-1] != 2:
        raise ValueError(f"positions must have shape (n, 2); got {arr.shape}")
    return arr


def raw_individual_pressure(
    defender_pos: ArrayLike,
    carrier_pos: ArrayLike,
    radius: float = DEFAULT_INFLUENCE_RADIUS_M,
) -> FloatArray:
    """Eq. 1 — raw individual pressure from one or more defenders on one carrier.

    Parameters
    ----------
    defender_pos : array-like, shape (n, 2) or (2,)
        Defender XY position(s) in metres.
    carrier_pos : array-like, shape (2,)
        Ball-carrier XY position.
    radius : float, default ``DEFAULT_INFLUENCE_RADIUS_M``
        Effective influence radius r (metres).

    Returns
    -------
    np.ndarray, shape (n,)
        Raw pressure values in m^2 (quadratic decay).
    """
    if radius <= 0:
        raise ValueError("radius must be > 0")
    D = _as_2d(defender_pos)
    c = _as_2d(carrier_pos)
    if c.shape[0] != 1:
        raise ValueError("carrier_pos must be a single point of shape (2,) or (1, 2)")
    d = np.linalg.norm(D - c, axis=1)
    within = d <= radius
    out = np.zeros_like(d)
    out[within] = (radius - d[within]) ** 2
    return out


def individual_unit_pressure(
    defender_pos: ArrayLike,
    carrier_pos: ArrayLike,
    radius: float = DEFAULT_INFLUENCE_RADIUS_M,
) -> FloatArray:
    """Eq. 2 — unit pressure, raw pressure normalized over the influence area."""
    raw = raw_individual_pressure(defender_pos, carrier_pos, radius=radius)
    return raw / (math.pi * radius**2)


def collective_pressure(
    defenders_pos: ArrayLike,
    carrier_pos: ArrayLike,
    radius: float = DEFAULT_INFLUENCE_RADIUS_M,
) -> float:
    """Eq. 3 — collective unit pressure from the whole defending team on the carrier."""
    return float(individual_unit_pressure(defenders_pos, carrier_pos, radius=radius).sum())


def mean_collective_pressure(
    defenders_pos_per_frame: Sequence[ArrayLike],
    carrier_pos_per_frame: Sequence[ArrayLike],
    radius: float = DEFAULT_INFLUENCE_RADIUS_M,
) -> float:
    """Eq. 4 — mean collective pressure over a possession sequence.

    Parameters
    ----------
    defenders_pos_per_frame : sequence of (n_f, 2) arrays
        Defender positions in each tracked frame of the sequence. Each frame may
        contain a different number of defenders (e.g. defenders leaving range).
    carrier_pos_per_frame : sequence of (2,) arrays
        Carrier position in each frame.
    radius : float
        Effective influence radius r.
    """
    frames = list(defenders_pos_per_frame)
    carriers = list(carrier_pos_per_frame)
    if len(frames) != len(carriers):
        raise ValueError("defenders and carrier frame sequences must be the same length")
    if not frames:
        return 0.0
    values = [
        collective_pressure(d, c, radius=radius) for d, c in zip(frames, carriers, strict=True)
    ]
    return float(np.mean(values))

"""Defensive Distortion Index — DDI (paper §3.4, Eq. 8).

    DDI(j) = integral over {x : xT(x) >= tau} [ Phi_{t+}(x) - Phi_{t-}(x) ] dx

where Phi is the pitch-control surface and tau is the high-value xT threshold
(paper default: 0.08).
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from athletiq.metrics.xt import XTGrid, default_xt_grid

FloatArray = npt.NDArray[np.floating]

DEFAULT_TAU: float = 0.08


def _xt_values_on_grid(xx: FloatArray, yy: FloatArray, grid: XTGrid) -> FloatArray:
    rows, cols = grid.shape
    col = np.clip(np.floor(xx / grid.pitch_length * cols).astype(np.int64), 0, cols - 1)
    row = np.clip(np.floor(yy / grid.pitch_width * rows).astype(np.int64), 0, rows - 1)
    return grid.values[row, col]


def ddi(
    phi_before: FloatArray,
    phi_after: FloatArray,
    xx: FloatArray,
    yy: FloatArray,
    xt_grid: XTGrid | None = None,
    tau: float = DEFAULT_TAU,
) -> float:
    """Eq. 8 — Defensive Distortion Index in m^2 of high-value space generated.

    All four arrays (phi_before, phi_after, xx, yy) must share the same shape.
    """
    if not (phi_before.shape == phi_after.shape == xx.shape == yy.shape):
        raise ValueError("phi_before, phi_after, xx, yy must share shape")

    g = xt_grid if xt_grid is not None else default_xt_grid()
    xt = _xt_values_on_grid(xx, yy, g)
    mask = xt >= tau

    delta = phi_after - phi_before
    # cell area from grid spacing
    if xx.shape[1] < 2 or xx.shape[0] < 2:
        raise ValueError("grid must be at least 2x2")
    dx = float(abs(xx[0, 1] - xx[0, 0]))
    dy = float(abs(yy[1, 0] - yy[0, 0]))
    cell_area = dx * dy

    return float((delta[mask]).sum() * cell_area)

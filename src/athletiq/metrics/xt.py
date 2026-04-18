"""Expected Threat (xT) — paper §3.3, Eq. 6.

A pitch is tiled into an ``M x N`` grid (paper's default: 16 x 12). Each cell is
assigned an empirical probability ``xT(z)`` of a goal being scored from it.
This module ships a sensible default xT grid (Karun Singh-style, symmetric
around the attacking goal) so the prototype is fully self-contained. Users may
drop in their own calibrated grid via ``set_xt_grid``.

Progressive Carry xT (Eq. 6):

    xT_carry = [ xT(z1) - xT(z0) ] * (1 + alpha * mean_pressure)

where ``alpha > 0`` is a per-cohort amplification coefficient.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from athletiq.metrics.types import PITCH_LENGTH_M, PITCH_WIDTH_M

FloatArray = npt.NDArray[np.floating]

DEFAULT_ALPHA: float = 0.5
"""Default pressure amplification coefficient (empirically calibratable)."""


@dataclass(frozen=True, slots=True)
class XTGrid:
    """An xT grid tiling the pitch into ``rows x cols`` cells.

    Attributes
    ----------
    values : (rows, cols) array of xT values in [0, 1].
    pitch_length : attacking-axis length (metres), cell[0, 0] is at (x=0, y=0).
    pitch_width : lateral-axis width (metres).
    """

    values: FloatArray
    pitch_length: float = PITCH_LENGTH_M
    pitch_width: float = PITCH_WIDTH_M

    @property
    def shape(self) -> tuple[int, int]:
        r, c = self.values.shape
        return int(r), int(c)

    def cell_of(self, x: float, y: float) -> tuple[int, int]:
        """Return (row, col) of the cell containing the point (x, y)."""
        rows, cols = self.shape
        # attacking direction = +x; rows tile y, cols tile x
        col = int(np.clip(np.floor(x / self.pitch_length * cols), 0, cols - 1))
        row = int(np.clip(np.floor(y / self.pitch_width * rows), 0, rows - 1))
        return row, col

    def value_at(self, x: float, y: float) -> float:
        r, c = self.cell_of(x, y)
        return float(self.values[r, c])


def default_xt_grid(rows: int = 12, cols: int = 16) -> XTGrid:
    """Build a default xT grid shaped like Karun Singh's canonical map.

    This is a synthetic but realistic surface: monotonically increasing with
    x (distance toward attacking goal) and peaking in the centre on the y-axis.
    For production use, replace with an empirically calibrated grid.
    """
    xs = (np.arange(cols) + 0.5) / cols  # 0..1 normalized x
    ys = (np.arange(rows) + 0.5) / rows  # 0..1 normalized y

    # x component: steep exponential growth toward goal
    x_comp = np.power(xs, 4.0)
    # y component: centred gaussian-ish bump, width 0.25
    y_comp = np.exp(-((ys - 0.5) ** 2) / (2 * 0.25**2))

    grid = np.outer(y_comp, x_comp)
    # normalize to roughly [0, 0.4] max (realistic empirical peak)
    grid = grid / grid.max() * 0.40
    return XTGrid(values=grid.astype(np.float64))


_DEFAULT_GRID: XTGrid | None = None


def _get_grid() -> XTGrid:
    global _DEFAULT_GRID
    if _DEFAULT_GRID is None:
        _DEFAULT_GRID = default_xt_grid()
    return _DEFAULT_GRID


def set_xt_grid(grid: XTGrid) -> None:
    """Override the process-global default xT grid."""
    global _DEFAULT_GRID
    _DEFAULT_GRID = grid


def xt_value_at(x: float, y: float, grid: XTGrid | None = None) -> float:
    """Return xT at the pitch point (x, y). Uses the default grid if none given."""
    g = grid if grid is not None else _get_grid()
    return g.value_at(x, y)


def progressive_carry_xt(
    start_xy: tuple[float, float],
    end_xy: tuple[float, float],
    mean_pressure: float,
    alpha: float = DEFAULT_ALPHA,
    grid: XTGrid | None = None,
) -> float:
    """Eq. 6 — pressure-weighted progressive carry xT.

    Returns 0.0 if the carry is regressive (end xT < start xT), matching the
    "progressive" qualifier in the paper's §3.3.
    """
    g = grid if grid is not None else _get_grid()
    delta = g.value_at(*end_xy) - g.value_at(*start_xy)
    if delta <= 0:
        return 0.0
    return float(delta * (1.0 + alpha * mean_pressure))

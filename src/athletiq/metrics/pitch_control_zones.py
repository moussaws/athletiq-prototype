"""Coach-facing zonal summary of a Pitch Control surface.

The raw ``pitch_control_surface`` output is a dense grid (34x52 by default) that
is technically correct but visually illegible for a coach. This module turns the
surface into a **12-tile zonal read** (4 channels x 3 thirds), plus three
hot/cold zones and an auto-generated headline verdict.

Conventions:

* The attacking team always attacks ``x = 0 -> x = pitch_length``; higher x is
  closer to the opponent goal.
* Channels are sliced along the ``y`` axis into four equal-width bands:
  left flank, left half-space, right half-space, right flank. (Standard 5-lane
  terminology is widely used in football coaching; we drop the central lane in
  favour of 4 symmetric channels so each tile stays a meaningful size.)
* Thirds are the classical defensive / middle / attacking thirds along the
  ``x`` axis.

The headline is phrased in coach language and is stable/deterministic given the
surface.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from athletiq.metrics.types import PITCH_LENGTH_M, PITCH_WIDTH_M

FloatArray = npt.NDArray[np.floating]

CHANNEL_NAMES: tuple[str, ...] = (
    "Left flank",
    "Left half-space",
    "Right half-space",
    "Right flank",
)
THIRD_NAMES: tuple[str, ...] = (
    "defensive third",
    "middle third",
    "attacking third",
)


@dataclass(frozen=True, slots=True)
class Zone:
    """One cell of the 4-channel x 3-third zonal grid."""

    channel_index: int  # 0..3, 0 = left flank
    third_index: int  # 0..2, 0 = defensive third (attacker's own half)
    channel: str
    third: str
    x_range: tuple[float, float]
    y_range: tuple[float, float]
    phi_mean: float  # attacker-dominance probability in [0, 1]

    @property
    def label(self) -> str:
        return f"{self.channel}, {self.third}"

    @property
    def x_center(self) -> float:
        return 0.5 * (self.x_range[0] + self.x_range[1])

    @property
    def y_center(self) -> float:
        return 0.5 * (self.y_range[0] + self.y_range[1])


@dataclass(frozen=True, slots=True)
class ZonalSummary:
    """Coach-readable digest of a pitch-control surface."""

    zones: list[Zone]
    channels: tuple[str, ...]
    thirds: tuple[str, ...]

    hottest_attack: Zone
    """Zone with the highest attacker dominance (where the attack owns most space)."""

    defensive_weak_point: Zone
    """Zone in the attacker's ATTACKING third with the LOWEST attacker dominance.

    Interpretation: of the zones where the attack ought to be threatening, this
    is where the defender holds firm -- i.e. the defender's strongest patch in
    the attacking third, equivalently the attacker's weakest attacking patch.
    """

    opportunity_zone: Zone
    """Zone in the attacker's DEFENSIVE third with the HIGHEST attacker dominance.

    Interpretation: territory the attacker already controls deep in their own
    half -- safe space to build from. Useful context for 'where do we start
    possession?' coaching questions.
    """

    balance_attacker_pct: float  # area-weighted mean phi, as percent (0..100)
    balance_defender_pct: float  # 100 - balance_attacker_pct

    headline: str  # one-sentence coach caption


def _slice_indices(n_cells: int, n_buckets: int) -> list[tuple[int, int]]:
    """Split ``n_cells`` evenly into ``n_buckets`` contiguous index slices.

    Any remainder is distributed to the first buckets. Returns half-open
    ``[start, end)`` pairs.
    """
    base, rem = divmod(n_cells, n_buckets)
    out: list[tuple[int, int]] = []
    cursor = 0
    for i in range(n_buckets):
        width = base + (1 if i < rem else 0)
        out.append((cursor, cursor + width))
        cursor += width
    return out


def _range_from_slice(
    axis: FloatArray,
    start: int,
    end: int,
    axis_length: float,
    n_cells: int,
) -> tuple[float, float]:
    """Convert an index slice on a grid axis to a physical metric range.

    ``axis`` values are cell-centres (``np.linspace(0.5, L - 0.5, n)``), so the
    cell width is ``L / n``. The physical range of the slice spans from the
    LEFT edge of the first cell to the RIGHT edge of the last cell.
    """
    cell = axis_length / n_cells
    lo = float(axis[start] - 0.5 * cell)
    hi = float(axis[end - 1] + 0.5 * cell)
    return (max(0.0, lo), min(axis_length, hi))


def zonal_summary(
    phi: FloatArray,
    xs: FloatArray,
    ys: FloatArray,
    pitch_length: float = PITCH_LENGTH_M,
    pitch_width: float = PITCH_WIDTH_M,
    n_channels: int = 4,
    n_thirds: int = 3,
) -> ZonalSummary:
    """Aggregate a pitch-control surface into a coach-readable zonal read.

    Parameters
    ----------
    phi : (H, W) array
        Attacker dominance surface from :func:`pitch_control_surface`.
    xs, ys : (W,) and (H,) or (H, W) arrays
        Grid coordinates. ``xs`` must be 1D along the x (third) axis;
        ``ys`` 1D along the y (channel) axis. If 2D meshgrid arrays are passed
        we extract the first row / column.
    pitch_length, pitch_width : float
        Physical pitch dimensions in metres (used for zone bounding boxes).
    n_channels, n_thirds : int
        Grid for the zonal read. Defaults 4 x 3 match the spec in the plan.

    Returns
    -------
    ZonalSummary
    """
    if phi.ndim != 2:
        raise ValueError(f"phi must be 2D, got shape {phi.shape}")
    if n_channels < 1 or n_thirds < 1:
        raise ValueError("n_channels and n_thirds must be >= 1")
    if n_channels != 4:
        # Allow the knob but keep default channel names meaningful.
        channels = tuple(f"Channel {i + 1}" for i in range(n_channels))
    else:
        channels = CHANNEL_NAMES
    thirds = (
        tuple(f"Third {i + 1}" for i in range(n_thirds))
        if n_thirds != 3
        else THIRD_NAMES
    )

    xs_1d = np.asarray(xs)
    ys_1d = np.asarray(ys)
    if xs_1d.ndim == 2:
        xs_1d = xs_1d[0, :]
    if ys_1d.ndim == 2:
        ys_1d = ys_1d[:, 0]

    H, W = phi.shape
    if xs_1d.shape != (W,) or ys_1d.shape != (H,):
        raise ValueError(
            f"xs/ys shape mismatch: phi={phi.shape}, xs={xs_1d.shape}, ys={ys_1d.shape}"
        )

    third_slices = _slice_indices(W, n_thirds)
    channel_slices = _slice_indices(H, n_channels)

    zones: list[Zone] = []
    for ci, (r0, r1) in enumerate(channel_slices):
        for ti, (c0, c1) in enumerate(third_slices):
            block = phi[r0:r1, c0:c1]
            mean_val = float(block.mean()) if block.size > 0 else float("nan")
            zones.append(
                Zone(
                    channel_index=ci,
                    third_index=ti,
                    channel=channels[ci],
                    third=thirds[ti],
                    x_range=_range_from_slice(xs_1d, c0, c1, pitch_length, W),
                    y_range=_range_from_slice(ys_1d, r0, r1, pitch_width, H),
                    phi_mean=mean_val,
                )
            )

    # Balance — area-weighted mean phi. Grid is uniform, so this is just the
    # raw mean of phi. We still compute it area-weighted for correctness under
    # non-uniform grids.
    cell_area = (pitch_length / W) * (pitch_width / H)
    total_area = cell_area * phi.size
    balance = float(phi.sum() * cell_area / total_area) * 100.0

    # Special zones
    hottest_attack = max(zones, key=lambda z: z.phi_mean)

    attacking_third_zones = [z for z in zones if z.third_index == n_thirds - 1]
    defensive_weak_point = min(attacking_third_zones, key=lambda z: z.phi_mean)

    defensive_third_zones = [z for z in zones if z.third_index == 0]
    opportunity_zone = max(defensive_third_zones, key=lambda z: z.phi_mean)

    headline = _headline(
        hottest_attack=hottest_attack,
        defensive_weak_point=defensive_weak_point,
        opportunity_zone=opportunity_zone,
        balance_attacker_pct=balance,
    )

    return ZonalSummary(
        zones=zones,
        channels=channels,
        thirds=thirds,
        hottest_attack=hottest_attack,
        defensive_weak_point=defensive_weak_point,
        opportunity_zone=opportunity_zone,
        balance_attacker_pct=balance,
        balance_defender_pct=100.0 - balance,
        headline=headline,
    )


def _headline(
    *,
    hottest_attack: Zone,
    defensive_weak_point: Zone,
    opportunity_zone: Zone,
    balance_attacker_pct: float,
) -> str:
    """Deterministic one-sentence coach caption from the zonal read.

    Three sentences, separated by spaces:
    1. Where the attack owns the most space.
    2. Where the defence is holding firm / where the attack is struggling most.
    3. Territorial balance or safe-build-up zone, depending on the balance.
    """
    atk = balance_attacker_pct
    def_pct = 100.0 - atk

    s1 = f"Attack owns the {hottest_attack.label.lower()} (Φ={hottest_attack.phi_mean:.2f})."

    # The "weak point" is the attacker's weakest zone inside the attacking
    # third -- i.e. the defence's strongest pocket in territory the attack
    # wants to occupy. Phrase it as the defence's strong patch.
    s2 = (
        f"Defence holds the {defensive_weak_point.label.lower()} "
        f"(Φ={defensive_weak_point.phi_mean:.2f})."
    )

    if atk >= 55.0:
        s3 = (
            f"Territorial balance: attacker {atk:.0f}% · defender {def_pct:.0f}% — "
            "attack should press its dominance."
        )
    elif atk <= 45.0:
        s3 = (
            f"Territorial balance: attacker {atk:.0f}% · defender {def_pct:.0f}% — "
            f"safest build-up from {opportunity_zone.label.lower()}."
        )
    else:
        s3 = (
            f"Territorial balance: attacker {atk:.0f}% · defender {def_pct:.0f}% — "
            "evenly contested."
        )

    return " ".join([s1, s2, s3])

"""Pillar A — context-aware spatial metrics.

Implements the equations from Section 3 of the AthletIQ paper:

* Eq. 1  — raw individual pressure ``P^r_{a,b} = (r - d)^2 if d <= r else 0``
* Eq. 2  — unit pressure ``p^r_{a,b} = P^r_{a,b} / (pi * r**2)``
* Eq. 3  — collective pressure ``P^r_{A,l} = sum_a p^r_{a,b}``
* Eq. 4  — mean collective pressure over a sequence
* Eq. 5  — Press-Adjusted Absolute Ball Retention (PABR)
* Eq. 6  — Progressive Carry xT: ``[xT(z1) - xT(z0)] * (1 + alpha * mean_P)``
* Eq. 7  — Pitch Control surface Phi(x) from time-to-intercept
* Eq. 8  — Defensive Distortion Index (DDI)
"""

from athletiq.metrics.ddi import ddi
from athletiq.metrics.pitch_control import pitch_control_surface
from athletiq.metrics.pitch_control_zones import ZonalSummary, Zone, zonal_summary
from athletiq.metrics.pressure import (
    collective_pressure,
    individual_unit_pressure,
    mean_collective_pressure,
    raw_individual_pressure,
)
from athletiq.metrics.retention import pabr
from athletiq.metrics.scenario import (
    VALID_FORMATIONS,
    ScenarioDiff,
    default_ball_position,
    defensive_line_height_m,
    diff_scenarios,
    formation_preset,
    phi_from_positions,
)
from athletiq.metrics.scenario_xg import (
    ScenarioXG,
    geometric_xg,
    scenario_xg,
    xg_surface,
)
from athletiq.metrics.xt import (
    default_xt_grid,
    progressive_carry_xt,
    xt_value_at,
)

__all__ = [
    "ScenarioDiff",
    "ScenarioXG",
    "VALID_FORMATIONS",
    "Zone",
    "ZonalSummary",
    "collective_pressure",
    "ddi",
    "default_ball_position",
    "default_xt_grid",
    "defensive_line_height_m",
    "diff_scenarios",
    "formation_preset",
    "geometric_xg",
    "individual_unit_pressure",
    "mean_collective_pressure",
    "pabr",
    "phi_from_positions",
    "pitch_control_surface",
    "progressive_carry_xt",
    "raw_individual_pressure",
    "scenario_xg",
    "xg_surface",
    "xt_value_at",
    "zonal_summary",
]

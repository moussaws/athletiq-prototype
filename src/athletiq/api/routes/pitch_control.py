"""Pitch Control + DDI endpoints."""

from __future__ import annotations

from typing import Literal

import numpy as np
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from athletiq.data.synthetic import generate_synthetic_snapshot
from athletiq.metrics import (
    VALID_FORMATIONS,
    ScenarioDiff,
    ScenarioXG,
    ddi,
    default_ball_position,
    defensive_line_height_m,
    diff_scenarios,
    formation_preset,
    phi_from_positions,
    pitch_control_surface,
    scenario_xg,
    zonal_summary,
)
from athletiq.metrics.pitch_control import PlayerSnapshot
from athletiq.metrics.pitch_control_zones import ZonalSummary, Zone

router = APIRouter()


class PlayerSnapshotIn(BaseModel):
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    team: int = 0


class PitchControlRequest(BaseModel):
    players: list[PlayerSnapshotIn]
    grid_rows: int = 34
    grid_cols: int = 52


class ZoneDTO(BaseModel):
    channel_index: int
    third_index: int
    channel: str
    third: str
    label: str
    x_range: tuple[float, float]
    y_range: tuple[float, float]
    x_center: float
    y_center: float
    phi_mean: float


class ZonalSummaryDTO(BaseModel):
    zones: list[ZoneDTO]
    channels: list[str]
    thirds: list[str]
    hottest_attack: ZoneDTO
    defensive_weak_point: ZoneDTO
    opportunity_zone: ZoneDTO
    balance_attacker_pct: float
    balance_defender_pct: float
    headline: str


class PitchControlResponse(BaseModel):
    phi: list[list[float]]
    xs: list[float]
    ys: list[float]
    zonal: ZonalSummaryDTO | None = None


def _zone_dto(z: Zone) -> ZoneDTO:
    return ZoneDTO(
        channel_index=z.channel_index,
        third_index=z.third_index,
        channel=z.channel,
        third=z.third,
        label=z.label,
        x_range=z.x_range,
        y_range=z.y_range,
        x_center=z.x_center,
        y_center=z.y_center,
        phi_mean=z.phi_mean,
    )


def _zonal_dto(s: ZonalSummary) -> ZonalSummaryDTO:
    return ZonalSummaryDTO(
        zones=[_zone_dto(z) for z in s.zones],
        channels=list(s.channels),
        thirds=list(s.thirds),
        hottest_attack=_zone_dto(s.hottest_attack),
        defensive_weak_point=_zone_dto(s.defensive_weak_point),
        opportunity_zone=_zone_dto(s.opportunity_zone),
        balance_attacker_pct=s.balance_attacker_pct,
        balance_defender_pct=s.balance_defender_pct,
        headline=s.headline,
    )


@router.post("", response_model=PitchControlResponse)
def compute_pitch_control(req: PitchControlRequest) -> PitchControlResponse:
    players = [PlayerSnapshot(**p.model_dump()) for p in req.players]
    phi, xx, yy = pitch_control_surface(players, grid_shape=(req.grid_rows, req.grid_cols))
    try:
        summary = zonal_summary(phi, xx[0], yy[:, 0])
        zonal = _zonal_dto(summary)
    except ValueError:
        # grid too small for 4x3 zonal aggregation — skip, keep raw Φ payload
        zonal = None
    return PitchControlResponse(
        phi=phi.tolist(),
        xs=xx[0].tolist(),
        ys=yy[:, 0].tolist(),
        zonal=zonal,
    )


@router.get("/demo", response_model=PitchControlResponse)
def demo_pitch_control(seed: int = Query(default=0)) -> PitchControlResponse:
    players = generate_synthetic_snapshot(seed=seed)
    phi, xx, yy = pitch_control_surface(players, grid_shape=(34, 52))
    summary = zonal_summary(phi, xx[0], yy[:, 0])
    return PitchControlResponse(
        phi=phi.tolist(),
        xs=xx[0].tolist(),
        ys=yy[:, 0].tolist(),
        zonal=_zonal_dto(summary),
    )


class DDIDemoResponse(BaseModel):
    ddi_m2: float
    tau: float


@router.get("/ddi-demo", response_model=DDIDemoResponse)
def demo_ddi(seed: int = 0, tau: float = 0.08) -> DDIDemoResponse:
    """Synthetic DDI demo: snapshot -> carrier steps into high-threat zone."""
    before = generate_synthetic_snapshot(seed=seed)
    # after: shift the ball-near attacker 8m forward and drag 2 defenders with them
    after = []
    shift = 0
    for p in before:
        if p.team == 0 and shift < 1 and p.x > 75:
            after.append(PlayerSnapshot(x=p.x + 5, y=p.y, vx=p.vx, vy=p.vy, team=0))
            shift += 1
        else:
            after.append(p)
    phi_b, xx, yy = pitch_control_surface(before, grid_shape=(34, 52))
    phi_a, _, _ = pitch_control_surface(after, grid_shape=(34, 52))
    val = ddi(np.array(phi_b), np.array(phi_a), xx, yy, tau=tau)
    return DDIDemoResponse(ddi_m2=val, tau=tau)


# ---------------------------------------------------------------------------
# Tactical Counterfactual Lab — scenario endpoint
# ---------------------------------------------------------------------------


class Point(BaseModel):
    x: float
    y: float

    def as_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)


class ScenarioBaseline(BaseModel):
    """Explicit baseline scenario for the Lab's \"since you opened the tool\" diff.

    Preferred over ``baseline_seed`` because a coach's baseline is the formation
    they loaded, not the demo seed. ``baseline_seed`` stays for backward compat.
    """

    attackers: list[Point] = Field(..., min_length=1, max_length=11)
    defenders: list[Point] = Field(..., min_length=1, max_length=11)
    ball: Point


class ScenarioRequest(BaseModel):
    attackers: list[Point] = Field(
        ..., min_length=1, max_length=11, description="Attacker positions (<= 11)."
    )
    defenders: list[Point] = Field(
        ..., min_length=1, max_length=11, description="Defender positions (<= 11)."
    )
    ball: Point = Field(..., description="Ball position (metres, on the pitch).")
    grid_rows: int = 34
    grid_cols: int = 52
    baseline_seed: int | None = Field(
        default=None,
        description=(
            "If provided, also return a diff against the seeded demo baseline. "
            "Set to null to skip diffing. Ignored when ``baseline`` is provided."
        ),
    )
    baseline: ScenarioBaseline | None = Field(
        default=None,
        description=(
            "Explicit baseline positions — preferred over baseline_seed. When set "
            "the response's ``diff`` compares the current positions to this baseline."
        ),
    )


class ScenarioDiffDTO(BaseModel):
    delta_phi_mean: float
    delta_phi_final_third: float
    delta_balance_attacker_pct: float
    delta_defensive_line_height_m: float
    per_zone_delta: list[float]
    headline: str
    baseline_xg_for: float
    baseline_xg_against: float
    scenario_xg_for: float
    scenario_xg_against: float
    delta_xg_for: float
    delta_xg_against: float
    delta_xg_net: float


class ScenarioXGDTO(BaseModel):
    """Scenario-level xG scalars returned every request (no baseline needed)."""

    xg_for: float
    xg_against: float
    xg_net: float


class ScenarioResponse(BaseModel):
    phi: list[list[float]]
    xs: list[float]
    ys: list[float]
    zonal: ZonalSummaryDTO | None = None
    diff: ScenarioDiffDTO | None = None
    defensive_line_height_m: float
    xg: ScenarioXGDTO


def _scenario_diff_dto(d: ScenarioDiff) -> ScenarioDiffDTO:
    return ScenarioDiffDTO(
        delta_phi_mean=d.delta_phi_mean,
        delta_phi_final_third=d.delta_phi_final_third,
        delta_balance_attacker_pct=d.delta_balance_attacker_pct,
        delta_defensive_line_height_m=d.delta_defensive_line_height_m,
        per_zone_delta=list(d.per_zone_delta),
        headline=d.headline,
        baseline_xg_for=d.baseline_xg_for,
        baseline_xg_against=d.baseline_xg_against,
        scenario_xg_for=d.scenario_xg_for,
        scenario_xg_against=d.scenario_xg_against,
        delta_xg_for=d.delta_xg_for,
        delta_xg_against=d.delta_xg_against,
        delta_xg_net=d.delta_xg_net,
    )


def _xg_dto(x: ScenarioXG) -> ScenarioXGDTO:
    return ScenarioXGDTO(
        xg_for=x.xg_for,
        xg_against=x.xg_against,
        xg_net=x.xg_net,
    )


@router.post("/scenario", response_model=ScenarioResponse)
def compute_scenario(req: ScenarioRequest) -> ScenarioResponse:
    """Recompute Φ for an edited scenario + optionally diff against a baseline seed.

    This is the core endpoint behind the Tactical Counterfactual Lab (`/lab`):
    given raw attacker, defender and ball positions it returns the attacker
    dominance grid, the 4×3 coach-facing zonal read, and (if ``baseline_seed``
    is set) the delta vs. that seeded demo snapshot.
    """
    atk = np.array([[p.x, p.y] for p in req.attackers], dtype=np.float64)
    dfn = np.array([[p.x, p.y] for p in req.defenders], dtype=np.float64)
    ball = (req.ball.x, req.ball.y)

    phi, xs, ys = phi_from_positions(
        atk,
        dfn,
        ball,
        grid_shape=(req.grid_rows, req.grid_cols),
    )

    try:
        summary = zonal_summary(phi, xs, ys)
        zonal = _zonal_dto(summary)
    except ValueError:
        summary = None
        zonal = None

    line_height = defensive_line_height_m(dfn)
    xg = scenario_xg(phi, xs, ys, ball=ball)

    diff: ScenarioDiffDTO | None = None
    if summary is not None and (req.baseline is not None or req.baseline_seed is not None):
        if req.baseline is not None:
            base_atk = np.array([[p.x, p.y] for p in req.baseline.attackers], dtype=np.float64)
            base_def_xy = np.array([[p.x, p.y] for p in req.baseline.defenders], dtype=np.float64)
            base_ball = (req.baseline.ball.x, req.baseline.ball.y)
            base_phi, base_xs_1d, base_ys_1d = phi_from_positions(
                base_atk,
                base_def_xy,
                base_ball,
                grid_shape=(req.grid_rows, req.grid_cols),
            )
        else:
            baseline_players = generate_synthetic_snapshot(seed=req.baseline_seed)
            base_phi_raw, base_xx_2d, base_yy_2d = pitch_control_surface(
                baseline_players, grid_shape=(req.grid_rows, req.grid_cols)
            )
            base_phi = np.asarray(base_phi_raw)
            base_xs_1d = base_xx_2d[0]
            base_ys_1d = base_yy_2d[:, 0]
            base_def_xy = np.array(
                [[p.x, p.y] for p in baseline_players if p.team == 1], dtype=np.float64
            )
        try:
            base_summary = zonal_summary(base_phi, base_xs_1d, base_ys_1d)
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=(
                    "grid too small for baseline diff — minimum grid_rows=4, grid_cols=3 required"
                ),
            ) from exc
        d = diff_scenarios(
            baseline=base_summary,
            scenario=summary,
            baseline_phi=base_phi,
            scenario_phi=phi,
            baseline_xs=base_xs_1d,
            scenario_xs=xs,
            baseline_defenders=base_def_xy,
            scenario_defenders=dfn,
            baseline_ball=base_ball if req.baseline is not None else (52.5, 34.0),
            scenario_ball=ball,
        )
        diff = _scenario_diff_dto(d)

    return ScenarioResponse(
        phi=phi.tolist(),
        xs=xs.tolist(),
        ys=ys.tolist(),
        zonal=zonal,
        diff=diff,
        defensive_line_height_m=line_height,
        xg=_xg_dto(xg),
    )


class FormationPresetResponse(BaseModel):
    formation: str
    role: Literal["attacker", "defender"]
    positions: list[Point]
    ball: Point
    valid_formations: list[str]


@router.get("/scenario/preset", response_model=FormationPresetResponse)
def get_formation_preset(
    formation: str = Query(default="4-3-3"),
    role: Literal["attacker", "defender"] = Query(default="attacker"),
) -> FormationPresetResponse:
    """Return template positions for a formation + role to seed `/lab`.

    The attacker template attacks toward ``+x`` (GK at low ``x``). The
    defender template is the mirror image, so seeding attackers + defenders
    with the same formation yields a realistic 11v11 starting position.
    """
    if formation not in VALID_FORMATIONS:
        raise HTTPException(
            status_code=422,
            detail=(f"Unknown formation {formation!r}. Valid: {sorted(VALID_FORMATIONS)}"),
        )
    positions = formation_preset(formation, role)
    ball = default_ball_position()
    return FormationPresetResponse(
        formation=formation,
        role=role,
        positions=[Point(x=x, y=y) for (x, y) in positions],
        ball=Point(x=ball[0], y=ball[1]),
        valid_formations=list(VALID_FORMATIONS),
    )

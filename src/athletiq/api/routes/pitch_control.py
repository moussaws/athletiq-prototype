"""Pitch Control + DDI endpoints."""

from __future__ import annotations

import numpy as np
from fastapi import APIRouter, Query
from pydantic import BaseModel

from athletiq.data.synthetic import generate_synthetic_snapshot
from athletiq.metrics import ddi, pitch_control_surface, zonal_summary
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

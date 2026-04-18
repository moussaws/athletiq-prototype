"""Pitch Control + DDI endpoints."""

from __future__ import annotations

import numpy as np
from fastapi import APIRouter, Query
from pydantic import BaseModel

from athletiq.data.synthetic import generate_synthetic_snapshot
from athletiq.metrics import ddi, pitch_control_surface
from athletiq.metrics.pitch_control import PlayerSnapshot

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


class PitchControlResponse(BaseModel):
    phi: list[list[float]]
    xs: list[float]
    ys: list[float]


@router.post("", response_model=PitchControlResponse)
def compute_pitch_control(req: PitchControlRequest) -> PitchControlResponse:
    players = [PlayerSnapshot(**p.model_dump()) for p in req.players]
    phi, xx, yy = pitch_control_surface(players, grid_shape=(req.grid_rows, req.grid_cols))
    return PitchControlResponse(
        phi=phi.tolist(),
        xs=xx[0].tolist(),
        ys=yy[:, 0].tolist(),
    )


@router.get("/demo", response_model=PitchControlResponse)
def demo_pitch_control(seed: int = Query(default=0)) -> PitchControlResponse:
    players = generate_synthetic_snapshot(seed=seed)
    phi, xx, yy = pitch_control_surface(players, grid_shape=(34, 52))
    return PitchControlResponse(
        phi=phi.tolist(),
        xs=xx[0].tolist(),
        ys=yy[:, 0].tolist(),
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

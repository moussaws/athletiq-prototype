"""Pillar A endpoints: pressure field, PABR, carry xT, DDI."""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from athletiq.data.synthetic import generate_synthetic_possession
from athletiq.metrics import (
    collective_pressure,
    individual_unit_pressure,
    mean_collective_pressure,
    pabr,
    progressive_carry_xt,
    raw_individual_pressure,
)
from athletiq.metrics.ddi_attribution import simulate_match_ddi
from athletiq.metrics.retention import PossessionSequence

router = APIRouter()


class Point2D(BaseModel):
    x: float
    y: float


class PressureRequest(BaseModel):
    defenders: list[Point2D]
    carrier: Point2D
    radius: float = 5.0


class PressureResponse(BaseModel):
    raw_individual: list[float]
    unit_individual: list[float]
    collective: float


@router.post("/pressure", response_model=PressureResponse)
def compute_pressure(req: PressureRequest) -> PressureResponse:
    defenders = [[d.x, d.y] for d in req.defenders]
    carrier = [req.carrier.x, req.carrier.y]
    raw = raw_individual_pressure(defenders, carrier, radius=req.radius)
    unit = individual_unit_pressure(defenders, carrier, radius=req.radius)
    coll = collective_pressure(defenders, carrier, radius=req.radius)
    return PressureResponse(
        raw_individual=raw.tolist(),
        unit_individual=unit.tolist(),
        collective=coll,
    )


class PABRSequence(BaseModel):
    mean_pressure: float = Field(..., ge=0.0)
    retained: bool


class PABRRequest(BaseModel):
    sequences: list[PABRSequence]


class PABRResponse(BaseModel):
    pabr: float
    n_sequences: int


@router.post("/pabr", response_model=PABRResponse)
def compute_pabr(req: PABRRequest) -> PABRResponse:
    seqs = [
        PossessionSequence(mean_pressure=s.mean_pressure, retained=s.retained)
        for s in req.sequences
    ]
    return PABRResponse(pabr=pabr(seqs), n_sequences=len(seqs))


class CarryXTRequest(BaseModel):
    start: Point2D
    end: Point2D
    mean_pressure: float = 0.0
    alpha: float = 0.5


class CarryXTResponse(BaseModel):
    xt_carry: float


@router.post("/carry-xt", response_model=CarryXTResponse)
def compute_carry_xt(req: CarryXTRequest) -> CarryXTResponse:
    val = progressive_carry_xt(
        start_xy=(req.start.x, req.start.y),
        end_xy=(req.end.x, req.end.y),
        mean_pressure=req.mean_pressure,
        alpha=req.alpha,
    )
    return CarryXTResponse(xt_carry=val)


class DemoSequenceResponse(BaseModel):
    """Canned demo: generate a synthetic possession and compute mean pressure + PABR."""

    pressure_level: float
    retained: bool
    n_frames: int
    mean_pressure: float


@router.get("/demo-sequence", response_model=DemoSequenceResponse)
def demo_sequence(
    pressure_level: float = 0.6,
    retained: bool = True,
    n_frames: int = 40,
    seed: int = 0,
) -> DemoSequenceResponse:
    seq = generate_synthetic_possession(
        n_frames=n_frames, retained=retained, pressure_level=pressure_level, seed=seed
    )
    mean_p = mean_collective_pressure(seq.defenders_pos, seq.carrier_pos)
    return DemoSequenceResponse(
        pressure_level=pressure_level,
        retained=retained,
        n_frames=n_frames,
        mean_pressure=mean_p,
    )


class DDILeaderboardRow(BaseModel):
    player_id: str
    name: str
    position: str
    ddi_m2: float
    actions: int
    avg_per_action: float


class DDILeaderboardResponse(BaseModel):
    seed: int
    n_actions: int
    tau: float
    total_ddi_m2: float
    items: list[DDILeaderboardRow]


@router.get("/ddi-leaderboard", response_model=DDILeaderboardResponse)
def ddi_leaderboard(
    seed: int = Query(default=0),
    n_actions: int = Query(default=60, ge=1, le=500),
    tau: float = Query(default=0.08, ge=0.0, le=1.0),
    limit: int = Query(default=20, ge=1, le=50),
) -> DDILeaderboardResponse:
    """Per-player DDI aggregated over a synthetic match of single-mover actions."""
    match = simulate_match_ddi(seed=seed, n_actions=n_actions, tau=tau)
    rows = [
        DDILeaderboardRow(
            player_id=p.player_id,
            name=p.name,
            position=p.position,
            ddi_m2=p.ddi_m2,
            actions=p.actions,
            avg_per_action=p.avg_per_action,
        )
        for p in match.leaderboard[:limit]
    ]
    return DDILeaderboardResponse(
        seed=match.seed,
        n_actions=match.n_actions,
        tau=match.tau,
        total_ddi_m2=match.total_ddi_m2,
        items=rows,
    )

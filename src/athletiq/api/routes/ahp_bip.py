"""AHP + WASPAS + BIP roster optimization endpoints (Eq. 12–18)."""

from __future__ import annotations

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from athletiq.api.state import _default_feature_names, get_store
from athletiq.scouting.ahp import ahp_weights, consistency_ratio
from athletiq.scouting.bip import optimize_squad
from athletiq.scouting.waspas import normalize_benefit, waspas_scores

router = APIRouter()


class AHPRequest(BaseModel):
    criteria: list[str] = Field(..., min_length=2, max_length=15)
    pairwise_matrix: list[list[float]]


class AHPResponse(BaseModel):
    criteria: list[str]
    weights: list[float]
    consistency_ratio: float
    is_consistent: bool


@router.post("/ahp", response_model=AHPResponse)
def compute_ahp(req: AHPRequest) -> AHPResponse:
    A = np.array(req.pairwise_matrix, dtype=np.float64)
    if A.shape != (len(req.criteria), len(req.criteria)):
        raise HTTPException(status_code=422, detail="pairwise_matrix shape mismatch")
    try:
        w = ahp_weights(A)
        cr = consistency_ratio(A)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return AHPResponse(
        criteria=req.criteria,
        weights=w.tolist(),
        consistency_ratio=cr,
        is_consistent=cr < 0.10,
    )


class BIPRequest(BaseModel):
    criteria: list[str]
    weights: list[float]
    formation: dict[str, int]
    budget: float = Field(..., gt=0)
    foreign_max: int = Field(..., ge=0)


class AssignmentOut(BaseModel):
    position: str
    player_id: str
    name: str
    nationality: str
    age: int
    market_value_m: float
    positional_fit: float


class BIPResponse(BaseModel):
    assignments: list[AssignmentOut]
    total_score: float
    squad_gap_position: str | None
    squad_gap_delta: float
    budget_used: float
    foreign_count: int


@router.post("", response_model=BIPResponse)
def compute_squad(req: BIPRequest) -> BIPResponse:
    store = get_store()
    feature_names = _default_feature_names()
    missing = [c for c in req.criteria if c not in feature_names]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"unknown criteria: {missing}. Available: {feature_names}",
        )
    if len(req.weights) != len(req.criteria):
        raise HTTPException(status_code=422, detail="weights length mismatch")
    if not np.isclose(sum(req.weights), 1.0, atol=1e-3):
        raise HTTPException(status_code=422, detail="weights must sum to 1")

    # Build Y for every (player, position) — here "position" space is the
    # requested formation's positions (e.g., GK, CB, CB, FB, ...).
    positions = list(req.formation.keys())
    N = len(store.players)
    P = len(positions)
    w = np.array(req.weights, dtype=np.float64)
    feat_idx = [feature_names.index(c) for c in req.criteria]

    Y = np.zeros((N, P), dtype=np.float64)
    raw_features_matrix = np.array(
        [[p.features.get(fn, 0.0) for fn in feature_names] for p in store.players],
        dtype=np.float64,
    )
    for pi, pos in enumerate(positions):
        # Only players playing at ``pos`` get a non-zero positional fit; others
        # inherit 0 so the BIP will never assign them there.
        eligible = np.array([p.position == pos for p in store.players])
        if not eligible.any():
            continue
        Y_pos = raw_features_matrix[eligible][:, feat_idx]
        Y_norm = normalize_benefit(Y_pos)
        scores = waspas_scores(Y_norm, w)
        Y[eligible, pi] = scores

    result = optimize_squad(
        Q=Y,
        player_ids=[p.player_id for p in store.players],
        positions=positions,
        formation=req.formation,
        foreign_flags=[p.is_foreign for p in store.players],
        market_values=[p.market_value_m for p in store.players],
        budget=req.budget,
        foreign_max=req.foreign_max,
    )

    by_id = {p.player_id: p for p in store.players}
    assignments: list[AssignmentOut] = []
    for pid, pos in result.assignments.items():
        p = by_id[pid]
        pi = positions.index(pos)
        j = [x.player_id for x in store.players].index(pid)
        assignments.append(
            AssignmentOut(
                position=pos,
                player_id=pid,
                name=p.name,
                nationality=p.nationality,
                age=p.age,
                market_value_m=p.market_value_m,
                positional_fit=float(Y[j, pi]),
            )
        )
    # sort so the dashboard displays the lineup consistently
    order = {pos: i for i, pos in enumerate(positions)}
    assignments.sort(key=lambda a: (order[a.position], -a.positional_fit))
    return BIPResponse(
        assignments=assignments,
        total_score=result.total_score,
        squad_gap_position=result.squad_gap_position,
        squad_gap_delta=result.squad_gap_delta,
        budget_used=result.budget_used,
        foreign_count=result.foreign_count,
    )

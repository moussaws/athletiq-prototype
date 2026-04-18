"""Persisted AHP preferences + saved squads.

Storage target is PostgreSQL via ``DATABASE_URL``; defaults to a file-backed
SQLite DB so the prototype runs zero-config.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from athletiq.db import AhpPreference, SavedSquad, get_db

router = APIRouter()


# ------------------------------ AHP preferences ------------------------------


class AhpPreferenceIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    criteria: list[str] = Field(..., min_length=2, max_length=15)
    pairwise_matrix: list[list[float]]
    weights: list[float]
    consistency_ratio: float
    is_consistent: bool


class AhpPreferenceOut(BaseModel):
    id: int
    name: str
    criteria: list[str]
    pairwise_matrix: list[list[float]]
    weights: list[float]
    consistency_ratio: float
    is_consistent: bool
    created_at: datetime


def _pref_to_out(p: AhpPreference) -> AhpPreferenceOut:
    return AhpPreferenceOut(
        id=p.id,
        name=p.name,
        criteria=list(p.criteria),
        pairwise_matrix=[list(row) for row in p.pairwise_matrix],
        weights=list(p.weights),
        consistency_ratio=p.consistency_ratio,
        is_consistent=bool(p.is_consistent),
        created_at=p.created_at,
    )


@router.post("/preferences", response_model=AhpPreferenceOut, status_code=201)
def create_preference(body: AhpPreferenceIn, db: Session = Depends(get_db)) -> AhpPreferenceOut:
    n = len(body.criteria)
    if len(body.pairwise_matrix) != n or any(len(r) != n for r in body.pairwise_matrix):
        raise HTTPException(status_code=422, detail="pairwise_matrix shape mismatch")
    if len(body.weights) != n:
        raise HTTPException(status_code=422, detail="weights length mismatch")
    row = AhpPreference(
        name=body.name,
        criteria=body.criteria,
        pairwise_matrix=body.pairwise_matrix,
        weights=body.weights,
        consistency_ratio=body.consistency_ratio,
        is_consistent=1 if body.is_consistent else 0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _pref_to_out(row)


@router.get("/preferences", response_model=list[AhpPreferenceOut])
def list_preferences(db: Session = Depends(get_db)) -> list[AhpPreferenceOut]:
    rows = (
        db.execute(select(AhpPreference).order_by(AhpPreference.created_at.desc())).scalars().all()
    )
    return [_pref_to_out(r) for r in rows]


@router.get("/preferences/{pref_id}", response_model=AhpPreferenceOut)
def get_preference(pref_id: int, db: Session = Depends(get_db)) -> AhpPreferenceOut:
    row = db.get(AhpPreference, pref_id)
    if row is None:
        raise HTTPException(status_code=404, detail="preference not found")
    return _pref_to_out(row)


@router.delete("/preferences/{pref_id}", status_code=204)
def delete_preference(pref_id: int, db: Session = Depends(get_db)) -> None:
    row = db.get(AhpPreference, pref_id)
    if row is None:
        raise HTTPException(status_code=404, detail="preference not found")
    db.delete(row)
    db.commit()


# -------------------------------- Saved squads -------------------------------


class SavedSquadAssignment(BaseModel):
    position: str
    player_id: str
    name: str
    nationality: str
    age: int
    market_value_m: float
    is_foreign: bool
    positional_fit: float


class SavedSquadIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    preference_id: int | None = None
    criteria: list[str]
    weights: list[float]
    formation: dict[str, int]
    budget: float = Field(..., gt=0)
    foreign_max: int = Field(..., ge=0)
    assignments: list[SavedSquadAssignment]
    total_score: float
    squad_gap_position: str | None = None
    squad_gap_delta: float = 0.0
    budget_used: float
    foreign_count: int


class SavedSquadOut(SavedSquadIn):
    id: int
    created_at: datetime


def _squad_to_out(s: SavedSquad) -> SavedSquadOut:
    return SavedSquadOut(
        id=s.id,
        name=s.name,
        preference_id=s.preference_id,
        criteria=list(s.criteria),
        weights=list(s.weights),
        formation=dict(s.formation),
        budget=s.budget,
        foreign_max=s.foreign_max,
        assignments=[SavedSquadAssignment(**a) for a in s.assignments],
        total_score=s.total_score,
        squad_gap_position=s.squad_gap_position,
        squad_gap_delta=s.squad_gap_delta,
        budget_used=s.budget_used,
        foreign_count=s.foreign_count,
        created_at=s.created_at,
    )


@router.post("/saved", response_model=SavedSquadOut, status_code=201)
def create_saved_squad(body: SavedSquadIn, db: Session = Depends(get_db)) -> SavedSquadOut:
    if body.preference_id is not None and db.get(AhpPreference, body.preference_id) is None:
        raise HTTPException(status_code=422, detail="preference_id does not exist")
    row = SavedSquad(
        name=body.name,
        preference_id=body.preference_id,
        criteria=body.criteria,
        weights=body.weights,
        formation=body.formation,
        budget=body.budget,
        foreign_max=body.foreign_max,
        assignments=[a.model_dump() for a in body.assignments],
        total_score=body.total_score,
        squad_gap_position=body.squad_gap_position,
        squad_gap_delta=body.squad_gap_delta,
        budget_used=body.budget_used,
        foreign_count=body.foreign_count,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _squad_to_out(row)


@router.get("/saved", response_model=list[SavedSquadOut])
def list_saved_squads(db: Session = Depends(get_db)) -> list[SavedSquadOut]:
    rows = db.execute(select(SavedSquad).order_by(SavedSquad.created_at.desc())).scalars().all()
    return [_squad_to_out(r) for r in rows]


@router.get("/saved/{squad_id}", response_model=SavedSquadOut)
def get_saved_squad(squad_id: int, db: Session = Depends(get_db)) -> SavedSquadOut:
    row = db.get(SavedSquad, squad_id)
    if row is None:
        raise HTTPException(status_code=404, detail="saved squad not found")
    return _squad_to_out(row)


@router.delete("/saved/{squad_id}", status_code=204)
def delete_saved_squad(squad_id: int, db: Session = Depends(get_db)) -> None:
    row = db.get(SavedSquad, squad_id)
    if row is None:
        raise HTTPException(status_code=404, detail="saved squad not found")
    db.delete(row)
    db.commit()

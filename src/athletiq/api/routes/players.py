"""Player catalog endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from athletiq.api.state import get_store

router = APIRouter()


class PlayerOut(BaseModel):
    player_id: str
    name: str
    position: str
    nationality: str
    age: int
    market_value_m: float
    is_foreign: bool
    features: dict[str, float]


class PlayerListResponse(BaseModel):
    total: int
    items: list[PlayerOut]


@router.get("", response_model=PlayerListResponse)
def list_players(
    position: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PlayerListResponse:
    store = get_store()
    items = [p for p in store.players if (position is None or p.position == position)]
    total = len(items)
    window = items[offset : offset + limit]
    return PlayerListResponse(
        total=total,
        items=[
            PlayerOut(
                player_id=p.player_id,
                name=p.name,
                position=p.position,
                nationality=p.nationality,
                age=p.age,
                market_value_m=p.market_value_m,
                is_foreign=p.is_foreign,
                features=p.features,
            )
            for p in window
        ],
    )


@router.get("/{player_id}", response_model=PlayerOut)
def get_player(player_id: str) -> PlayerOut:
    store = get_store()
    for p in store.players:
        if p.player_id == player_id:
            return PlayerOut(
                player_id=p.player_id,
                name=p.name,
                position=p.position,
                nationality=p.nationality,
                age=p.age,
                market_value_m=p.market_value_m,
                is_foreign=p.is_foreign,
                features=p.features,
            )
    raise HTTPException(status_code=404, detail=f"player {player_id} not found")

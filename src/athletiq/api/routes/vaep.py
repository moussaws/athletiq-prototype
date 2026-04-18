"""VAEP-lite endpoint — per-player action-value leaderboard on StatsBomb events."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from athletiq.data import statsbomb as sb_mod
from athletiq.metrics.vaep import match_vaep

router = APIRouter()


class PlayerVAEPOut(BaseModel):
    player_id: str
    name: str
    team: str
    position: str
    n_actions: int
    vaep: float
    offensive_vaep: float
    defensive_vaep: float


class MatchVAEPResponse(BaseModel):
    match_id: int
    k_horizon: int
    n_actions: int
    n_goals: int
    players: list[PlayerVAEPOut]
    verdict: str


def _verdict(mv_players: list[PlayerVAEPOut], n_goals: int, n_actions: int) -> str:
    if not mv_players:
        return "No on-ball actions recorded in this match."
    top = mv_players[0]
    if n_goals == 0:
        return (
            f"No goals in the sampled window. VAEP-lite fell back to a flat "
            f"prior over {n_actions} actions — rankings are near-zero. "
            f"Re-run on a match with finishes for meaningful values."
        )
    # Scale the "how big" commentary to the numeric spread
    return (
        f"{top.name} ({top.team}, {top.position}) generated the highest action "
        f"value across {top.n_actions} on-ball events "
        f"(VAEP-lite {top.vaep:+.3f}, offensive {top.offensive_vaep:+.3f}, "
        f"defensive {top.defensive_vaep:+.3f})."
    )


@router.get("/match/{match_id}", response_model=MatchVAEPResponse)
def vaep_match(
    match_id: int,
    k: int = Query(default=10, ge=1, le=30),
) -> MatchVAEPResponse:
    if not sb_mod.STATSBOMB_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="statsbombpy not installed. `pip install -e '.[statsbomb]'`"
        )
    try:
        mv = match_vaep(match_id, k=k)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"VAEP failed: {e}") from e
    players = [
        PlayerVAEPOut(
            player_id=p.player_id,
            name=p.name,
            team=p.team,
            position=p.position,
            n_actions=p.n_actions,
            vaep=p.vaep,
            offensive_vaep=p.offensive_vaep,
            defensive_vaep=p.defensive_vaep,
        )
        for p in mv.players
    ]
    return MatchVAEPResponse(
        match_id=mv.match_id,
        k_horizon=mv.k_horizon,
        n_actions=mv.n_actions,
        n_goals=mv.n_goals,
        players=players,
        verdict=_verdict(players, mv.n_goals, mv.n_actions),
    )

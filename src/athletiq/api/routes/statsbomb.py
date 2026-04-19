"""StatsBomb open-data endpoints: competitions, matches, and per-match cohorts.

These routes plug the ``athletiq.data.statsbomb`` adapter into the API so
the dashboard can browse the real open dataset and run the Pillar B
pipeline (PCA / KNN / AHP / WASPAS / BIP) against a real match cohort
instead of the synthetic one.
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from athletiq.data import statsbomb as sb_mod
from athletiq.insights import build_match_narrative

router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────
class CapabilitiesResponse(BaseModel):
    statsbomb_available: bool
    reason: str | None


class CompetitionOut(BaseModel):
    competition_id: int
    season_id: int
    country_name: str
    competition_name: str
    season_name: str
    competition_gender: str


class CompetitionsResponse(BaseModel):
    items: list[CompetitionOut]
    total: int


class MatchOut(BaseModel):
    match_id: int
    competition_id: int
    season_id: int
    match_date: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int


class MatchesResponse(BaseModel):
    items: list[MatchOut]
    total: int


class MatchPlayerOut(BaseModel):
    player_id: str
    name: str
    position: str
    team: str
    age: int
    market_value_m: float
    passes_completed: float
    take_ons: float
    shots: float
    tackles: float
    interceptions: float
    xt_carry: float


class MatchCohortResponse(BaseModel):
    match_id: int
    home_team: str
    away_team: str
    score: str
    players: list[MatchPlayerOut]
    imputed_features: list[str]


class TopPerformerOut(BaseModel):
    role: str
    player_id: str
    name: str
    position: str
    metric_label: str
    value: float
    verdict: str


class TeamSummaryOut(BaseModel):
    team: str
    players_count: int
    total_passes: float
    total_shots: float
    total_take_ons: float
    total_defensive_actions: float
    total_xt_carry: float
    summary: str
    top_performers: list[TopPerformerOut]


class MatchNarrativeResponse(BaseModel):
    match_id: int
    home_team: str
    away_team: str
    score: str
    headline: str
    teams: list[TeamSummaryOut]
    imputed_features: list[str]


# ─── Routes ───────────────────────────────────────────────────────────
@router.get("/capabilities", response_model=CapabilitiesResponse)
def capabilities() -> CapabilitiesResponse:
    if sb_mod.statsbomb_available():
        return CapabilitiesResponse(statsbomb_available=True, reason=None)
    return CapabilitiesResponse(
        statsbomb_available=False,
        reason="statsbombpy not installed. Run `pip install -e '.[statsbomb]'`.",
    )


@router.get("/competitions", response_model=CompetitionsResponse)
def competitions() -> CompetitionsResponse:
    if not sb_mod.statsbomb_available():
        raise HTTPException(status_code=503, detail="statsbombpy not installed")
    try:
        comps = sb_mod.list_competitions()
    except Exception as e:  # network / upstream failure
        raise HTTPException(status_code=502, detail=f"StatsBomb upstream error: {e}") from e
    items = [CompetitionOut(**asdict(c)) for c in comps]
    return CompetitionsResponse(items=items, total=len(items))


@router.get("/matches", response_model=MatchesResponse)
def matches(
    competition_id: int = Query(..., ge=1),
    season_id: int = Query(..., ge=1),
) -> MatchesResponse:
    if not sb_mod.statsbomb_available():
        raise HTTPException(status_code=503, detail="statsbombpy not installed")
    try:
        ms = sb_mod.list_matches(competition_id, season_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"StatsBomb upstream error: {e}") from e
    items = [MatchOut(**asdict(m)) for m in ms]
    return MatchesResponse(items=items, total=len(items))


# StatsBomb event features that cannot be observed from open data and
# are imputed to position means downstream. Surfaced in the API so the
# UI can be honest about what is measured vs. inferred.
_IMPUTED_FEATURES = [
    "aerial_duels_won",
    "sprint_count",
    "accel_count",
    "pabr",
    "ddi",
]


@router.get("/match/{match_id}", response_model=MatchCohortResponse)
def match_cohort(match_id: int) -> MatchCohortResponse:
    if not sb_mod.statsbomb_available():
        raise HTTPException(status_code=503, detail="statsbombpy not installed")
    try:
        players = sb_mod.load_match_players(match_id)
        ms_for_meta = _resolve_match_meta(match_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"StatsBomb upstream error: {e}") from e
    if not players:
        raise HTTPException(status_code=404, detail=f"no events for match {match_id}")

    out_players: list[MatchPlayerOut] = []
    for p in players:
        out_players.append(
            MatchPlayerOut(
                player_id=p.player_id,
                name=p.name,
                position=p.position,
                team=p.nationality,
                age=p.age,
                market_value_m=p.market_value_m,
                passes_completed=p.features.get("passes_completed", 0.0),
                take_ons=p.features.get("take_ons", 0.0),
                shots=p.features.get("shots", 0.0),
                tackles=p.features.get("tackles", 0.0),
                interceptions=p.features.get("interceptions", 0.0),
                xt_carry=p.features.get("xt_carry", 0.0),
            )
        )

    home = ms_for_meta.home_team if ms_for_meta else ""
    away = ms_for_meta.away_team if ms_for_meta else ""
    score = f"{ms_for_meta.home_score}-{ms_for_meta.away_score}" if ms_for_meta else ""
    return MatchCohortResponse(
        match_id=match_id,
        home_team=home,
        away_team=away,
        score=score,
        players=out_players,
        imputed_features=_IMPUTED_FEATURES,
    )


@router.get("/match/{match_id}/insights", response_model=MatchNarrativeResponse)
def match_insights(match_id: int) -> MatchNarrativeResponse:
    """Coach-facing narrative for a StatsBomb match.

    Returns the same event-derived features as ``/match/{id}`` but
    re-shaped into a story: headline, per-team totals + one-sentence
    summary, top performers by role (creator / ball carrier / finisher /
    defensive worker / passer). The raw per-player table is still
    available via the ``/match/{id}`` endpoint for analyst view.
    """
    if not sb_mod.statsbomb_available():
        raise HTTPException(status_code=503, detail="statsbombpy not installed")
    try:
        players = sb_mod.load_match_players(match_id)
        ms_for_meta = _resolve_match_meta(match_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"StatsBomb upstream error: {e}") from e
    if not players:
        raise HTTPException(status_code=404, detail=f"no events for match {match_id}")

    home = ms_for_meta.home_team if ms_for_meta else ""
    away = ms_for_meta.away_team if ms_for_meta else ""
    score = f"{ms_for_meta.home_score}-{ms_for_meta.away_score}" if ms_for_meta else ""

    out_players: list[MatchPlayerOut] = []
    for p in players:
        out_players.append(
            MatchPlayerOut(
                player_id=p.player_id,
                name=p.name,
                position=p.position,
                team=p.nationality,
                age=p.age,
                market_value_m=p.market_value_m,
                passes_completed=p.features.get("passes_completed", 0.0),
                take_ons=p.features.get("take_ons", 0.0),
                shots=p.features.get("shots", 0.0),
                tackles=p.features.get("tackles", 0.0),
                interceptions=p.features.get("interceptions", 0.0),
                xt_carry=p.features.get("xt_carry", 0.0),
            )
        )
    narrative = build_match_narrative(
        match_id=match_id,
        home_team=home,
        away_team=away,
        score=score,
        players=out_players,
    )
    return MatchNarrativeResponse(
        match_id=narrative.match_id,
        home_team=narrative.home_team,
        away_team=narrative.away_team,
        score=narrative.score,
        headline=narrative.headline,
        teams=[
            TeamSummaryOut(
                team=t.team,
                players_count=t.players_count,
                total_passes=t.total_passes,
                total_shots=t.total_shots,
                total_take_ons=t.total_take_ons,
                total_defensive_actions=t.total_defensive_actions,
                total_xt_carry=t.total_xt_carry,
                summary=t.summary,
                top_performers=[
                    TopPerformerOut(
                        role=perf.role,
                        player_id=perf.player_id,
                        name=perf.name,
                        position=perf.position,
                        metric_label=perf.metric_label,
                        value=perf.value,
                        verdict=perf.verdict,
                    )
                    for perf in t.top_performers
                ],
            )
            for t in narrative.teams
        ],
        imputed_features=_IMPUTED_FEATURES,
    )


def _resolve_match_meta(match_id: int) -> sb_mod.StatsBombMatch | None:
    """Best-effort lookup of match metadata (teams + score) for a match_id.

    StatsBomb's API doesn't expose ``/match/<id>`` directly — metadata
    lives on the per-season matches endpoint. We infer (competition,
    season) from the player adapter's first row's team context and scan
    the most common seasons. Returns ``None`` if we can't find it.
    """
    # Small curated scan — WC 2022, WC 2018, Euro 2020, La Liga 2020/21,
    # La Liga 2015/16 (Messi dataset), Premier League 2015/16, Women's WC
    # 2023 — this covers the matches users are most likely to browse.
    candidates = [
        (43, 106),  # FIFA World Cup 2022
        (43, 3),  # FIFA World Cup 2018
        (55, 43),  # Euro 2020
        (11, 90),  # La Liga 2020/21
        (11, 27),  # La Liga 2015/16
        (2, 27),  # Premier League 2015/16
        (72, 107),  # Women's World Cup 2023
        (9, 281),  # Bundesliga 2023/24
    ]
    for cid, sid in candidates:
        try:
            for m in sb_mod.list_matches(cid, sid):
                if m.match_id == match_id:
                    return m
        except Exception:
            continue
    return None

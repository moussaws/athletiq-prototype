"""Coach-facing match narrative builder.

Given the flat per-player per-match rows returned by the StatsBomb adapter
(or any source with the same event-derived feature schema), produce a
narrative structure the dashboard can render without doing any analytics
itself.

No new model: this module only re-shapes, ranks and verbalises data that
already exists upstream. The raw tables remain available to callers that
want them (analyst view).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol


class MatchPlayerLike(Protocol):
    player_id: str
    name: str
    position: str
    team: str
    passes_completed: float
    take_ons: float
    shots: float
    tackles: float
    interceptions: float
    xt_carry: float


@dataclass(frozen=True)
class TopPerformer:
    role: str  # "Creator", "Finisher", "Ball carrier", "Defensive worker", "Passer"
    player_id: str
    name: str
    position: str
    metric_label: str  # e.g. "xT carry"
    value: float
    verdict: str  # one-sentence coach phrasing


@dataclass(frozen=True)
class TeamSummary:
    team: str
    players_count: int
    total_passes: float
    total_shots: float
    total_take_ons: float
    total_defensive_actions: float  # tackles + interceptions
    total_xt_carry: float
    summary: str  # one sentence
    top_performers: list[TopPerformer]


@dataclass(frozen=True)
class MatchNarrative:
    match_id: int
    home_team: str
    away_team: str
    score: str
    headline: str
    teams: list[TeamSummary]


def _safe(v: float) -> float:
    return 0.0 if v != v else float(v)  # NaN-safe


def _team_totals(players: list[MatchPlayerLike]) -> dict[str, float]:
    return {
        "passes": sum(_safe(p.passes_completed) for p in players),
        "shots": sum(_safe(p.shots) for p in players),
        "take_ons": sum(_safe(p.take_ons) for p in players),
        "defensive": sum(_safe(p.tackles) + _safe(p.interceptions) for p in players),
        "xt": sum(_safe(p.xt_carry) for p in players),
    }


def _top(
    players: list[MatchPlayerLike],
    scorer: str | Callable[[MatchPlayerLike], float],
    role: str,
    metric_label: str,
) -> TopPerformer | None:
    score: Callable[[MatchPlayerLike], float] = (
        (lambda p: _safe(getattr(p, scorer))) if isinstance(scorer, str) else scorer
    )
    best: MatchPlayerLike | None = None
    best_val = -1.0
    for p in players:
        v = score(p)
        if v > best_val:
            best_val = v
            best = p
    if best is None or best_val <= 0:
        return None
    return TopPerformer(
        role=role,
        player_id=best.player_id,
        name=best.name,
        position=best.position,
        metric_label=metric_label,
        value=best_val,
        verdict=_verbalise(role, best.position, metric_label, best_val),
    )


def _verbalise(role: str, position: str, metric_label: str, value: float) -> str:
    rounded = f"{value:.2f}" if "xT" in metric_label else f"{value:.0f}"
    phrasings = {
        "Creator": f"led the team for carrying into dangerous areas ({rounded} xT).",
        "Ball carrier": f"attempted the most take-ons ({rounded}) — the team's 1-v-1 outlet.",
        "Finisher": f"took the most shots ({rounded}) — primary goal threat.",
        "Defensive worker": (f"did the most defensive work ({rounded} tackles + interceptions)."),
        "Passer": f"completed the most passes ({rounded}) — midfield anchor for ball circulation.",
    }
    return phrasings.get(role, f"led {metric_label.lower()} ({rounded}).")


def _team_story(totals: dict[str, float], other_totals: dict[str, float]) -> str:
    bits: list[str] = []
    if totals["xt"] > other_totals["xt"] * 1.15:
        bits.append("carried the ball into dangerous areas far more than their opponent")
    elif totals["xt"] < other_totals["xt"] * 0.85:
        bits.append(
            "struggled to progress the ball into high-threat zones compared to their opponent"
        )
    if totals["shots"] > other_totals["shots"] * 1.3:
        bits.append(
            f"out-shot the opposition ({totals['shots']:.0f} vs {other_totals['shots']:.0f})"
        )
    if totals["defensive"] > other_totals["defensive"] * 1.2:
        bits.append(
            f"won the defensive exchanges ({totals['defensive']:.0f} tackles+interceptions)"
        )
    if not bits:
        bits.append("produced a balanced performance across passing, shooting and defensive work")
    return "They " + "; ".join(bits) + "."


def _match_headline(
    home: str, away: str, score: str, home_totals: dict[str, float], away_totals: dict[str, float]
) -> str:
    if home_totals["xt"] > away_totals["xt"] * 1.2:
        dominant, dominated = home, away
    elif away_totals["xt"] > home_totals["xt"] * 1.2:
        dominant, dominated = away, home
    else:
        dominant = dominated = ""
    score_str = f" ({score})" if score else ""
    if dominant:
        return (
            f"{home} vs {away}{score_str}: {dominant} controlled territorial threat over "
            f"{dominated}, generating more dangerous carries into the final third."
        )
    return (
        f"{home} vs {away}{score_str}: evenly-matched in terms of territorial threat — "
        "neither side decisively out-created the other in dangerous carries."
    )


def build_match_narrative(
    match_id: int,
    home_team: str,
    away_team: str,
    score: str,
    players: Iterable[MatchPlayerLike],
) -> MatchNarrative:
    roster = list(players)
    home_players = [p for p in roster if p.team == home_team]
    away_players = [p for p in roster if p.team == away_team]
    # If team names don't match (edge case — metadata labels differ from the
    # event-team strings), fall back to the first unique team labels seen in
    # the roster regardless of whether the caller's names were truthy.
    if not home_players and not away_players and roster:
        teams = []
        for p in roster:
            if p.team not in teams:
                teams.append(p.team)
        home_team = teams[0] if teams else (home_team or "Home")
        away_team = teams[1] if len(teams) > 1 else (away_team or "Away")
        home_players = [p for p in roster if p.team == home_team]
        away_players = [p for p in roster if p.team == away_team]

    home_totals = _team_totals(home_players)
    away_totals = _team_totals(away_players)

    def _team_summary(
        team_name: str,
        players_: list[MatchPlayerLike],
        totals: dict[str, float],
        other: dict[str, float],
    ) -> TeamSummary:
        performers = [
            _top(players_, "xt_carry", "Creator", "xT carry"),
            _top(players_, "take_ons", "Ball carrier", "take-ons"),
            _top(players_, "shots", "Finisher", "shots"),
            _top(
                players_,
                lambda p: _safe(p.tackles) + _safe(p.interceptions),
                "Defensive worker",
                "tackles + interceptions",
            ),
            _top(players_, "passes_completed", "Passer", "passes completed"),
        ]
        return TeamSummary(
            team=team_name or "Unknown",
            players_count=len(players_),
            total_passes=totals["passes"],
            total_shots=totals["shots"],
            total_take_ons=totals["take_ons"],
            total_defensive_actions=totals["defensive"],
            total_xt_carry=totals["xt"],
            summary=_team_story(totals, other),
            top_performers=[p for p in performers if p is not None],
        )

    teams = [
        _team_summary(home_team, home_players, home_totals, away_totals),
        _team_summary(away_team, away_players, away_totals, home_totals),
    ]
    headline = _match_headline(home_team, away_team, score, home_totals, away_totals)
    return MatchNarrative(
        match_id=match_id,
        home_team=home_team,
        away_team=away_team,
        score=score,
        headline=headline,
        teams=teams,
    )

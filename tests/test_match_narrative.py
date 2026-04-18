"""Tests for the match-narrative builder (coach-facing story for a match)."""

from __future__ import annotations

from dataclasses import dataclass

from athletiq.insights.match import build_match_narrative


@dataclass
class _P:
    player_id: str
    name: str
    position: str
    team: str
    passes_completed: float = 0.0
    take_ons: float = 0.0
    shots: float = 0.0
    tackles: float = 0.0
    interceptions: float = 0.0
    xt_carry: float = 0.0


def _home_players() -> list[_P]:
    return [
        _P("a1", "Abdul Passer", "CM", "Home", passes_completed=80, xt_carry=0.12),
        _P("a2", "Binyamin Runner", "WG", "Home", take_ons=9, xt_carry=0.45, shots=3),
        _P("a3", "Carlos Destroyer", "CB", "Home", tackles=6, interceptions=5),
        _P("a4", "Darko Finisher", "ST", "Home", shots=6, xt_carry=0.22),
    ]


def _away_players() -> list[_P]:
    return [
        _P("b1", "Eli Keeper", "GK", "Away"),
        _P("b2", "Felipe Backup", "CM", "Away", passes_completed=40, xt_carry=0.05),
        _P("b3", "Gio Pivot", "DM", "Away", tackles=2, interceptions=2),
        _P("b4", "Hiro Striker", "ST", "Away", shots=2, xt_carry=0.03),
    ]


def test_narrative_has_teams_and_top_performers():
    n = build_match_narrative(
        match_id=1,
        home_team="Home",
        away_team="Away",
        score="3-0",
        players=_home_players() + _away_players(),
    )
    assert n.home_team == "Home" and n.away_team == "Away"
    assert len(n.teams) == 2
    home, away = n.teams
    assert home.team == "Home"
    # Creator should be whoever has highest xt_carry on that team.
    creators = [p for p in home.top_performers if p.role == "Creator"]
    assert creators and creators[0].name == "Binyamin Runner"
    # Defensive worker is tackles-top.
    dw = [p for p in home.top_performers if p.role == "Defensive worker"]
    assert dw and dw[0].name == "Carlos Destroyer"
    # Finisher is shots-top.
    fin = [p for p in home.top_performers if p.role == "Finisher"]
    assert fin and fin[0].name == "Darko Finisher"


def test_headline_reflects_dominant_team():
    n = build_match_narrative(
        match_id=2,
        home_team="Home",
        away_team="Away",
        score="3-0",
        players=_home_players() + _away_players(),
    )
    assert "Home" in n.headline and "Away" in n.headline
    # Home total xt ≈ 0.79, Away ≈ 0.08 → Home dominates.
    assert "Home controlled territorial threat" in n.headline


def test_headline_balanced_when_similar():
    players = [
        _P("h1", "One", "CM", "Home", xt_carry=0.30),
        _P("a1", "Two", "CM", "Away", xt_carry=0.32),
    ]
    n = build_match_narrative(
        match_id=3,
        home_team="Home",
        away_team="Away",
        score="1-1",
        players=players,
    )
    assert "evenly-matched" in n.headline


def test_top_performer_skipped_when_no_activity():
    # Team with literally zero stats — no top performers should be returned.
    players = [_P("z1", "Zero", "CM", "Home")]
    n = build_match_narrative(
        match_id=4,
        home_team="Home",
        away_team="Away",
        score="",
        players=players,
    )
    home = n.teams[0]
    assert home.top_performers == []


def test_defensive_worker_uses_combined_tackles_and_interceptions():
    # Tackler has 4 tackles + 0 int = 4. Interceptor has 1 tackle + 8 int = 9.
    # Combined metric should pick Interceptor and report the sum (9).
    players = [
        _P("h1", "Tackler", "CB", "Home", tackles=4, interceptions=0),
        _P("h2", "Interceptor", "DM", "Home", tackles=1, interceptions=8),
    ]
    n = build_match_narrative(
        match_id=6,
        home_team="Home",
        away_team="Away",
        score="",
        players=players,
    )
    dw = [p for p in n.teams[0].top_performers if p.role == "Defensive worker"]
    assert dw and dw[0].name == "Interceptor"
    assert dw[0].value == 9
    assert "9 tackles + interceptions" in dw[0].verdict


def test_team_totals_match_inputs():
    n = build_match_narrative(
        match_id=5,
        home_team="Home",
        away_team="Away",
        score="",
        players=_home_players() + _away_players(),
    )
    home = n.teams[0]
    assert home.total_shots == 9  # 3 + 6
    assert home.total_passes == 80
    assert home.total_take_ons == 9
    assert home.total_defensive_actions == 11  # 6 + 5
    assert abs(home.total_xt_carry - (0.12 + 0.45 + 0.22)) < 1e-6

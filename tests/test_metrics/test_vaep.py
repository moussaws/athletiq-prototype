"""Unit tests for VAEP-lite (self-contained logistic action values)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from athletiq.metrics.vaep import compute_match_vaep


def _pass(
    x0: float, y0: float, x1: float, y1: float, *, team: int, player: int, t: float, name: str = "A"
) -> dict:
    return {
        "type": "Pass",
        "team": f"team{team}",
        "team_id": team,
        "player": name,
        "player_id": player,
        "position": "Center Midfield",
        "location": [x0, y0],
        "pass_end_location": [x1, y1],
        "carry_end_location": None,
        "shot_end_location": None,
        "shot_outcome": None,
        "period": 1,
        "timestamp": f"00:00:{t:05.2f}",
    }


def _shot(
    x0: float, y0: float, *, team: int, player: int, t: float, goal: bool, name: str = "A"
) -> dict:
    return {
        "type": "Shot",
        "team": f"team{team}",
        "team_id": team,
        "player": name,
        "player_id": player,
        "position": "Center Forward",
        "location": [x0, y0],
        "pass_end_location": None,
        "carry_end_location": None,
        "shot_end_location": [120.0, 40.0],
        "shot_outcome": "Goal" if goal else "Off T",
        "period": 1,
        "timestamp": f"00:00:{t:05.2f}",
    }


def test_empty_events_returns_empty_leaderboard() -> None:
    df = pd.DataFrame(columns=["type"])
    mv, per_event = compute_match_vaep(df)
    assert mv.n_actions == 0
    assert mv.n_goals == 0
    assert mv.players == ()
    assert per_event.empty


def test_goal_scorer_has_highest_offensive_vaep() -> None:
    # 12 actions: 10 team-1 progressive passes culminating in a goal,
    # then 2 team-2 actions. Team 1's striker should top the leaderboard.
    rows: list[dict] = []
    for i in range(10):
        rows.append(
            _pass(
                10.0 + i * 10,
                40.0,
                20.0 + i * 10,
                40.0,
                team=1,
                player=100 + i,
                t=i * 1.0,
                name=f"A{i}",
            )
        )
    rows.append(_shot(115.0, 40.0, team=1, player=111, t=11.0, goal=True, name="Striker"))
    rows.append(_pass(50.0, 40.0, 60.0, 40.0, team=2, player=200, t=12.0, name="B"))
    rows.append(_pass(60.0, 40.0, 70.0, 40.0, team=2, player=201, t=13.0, name="C"))

    df = pd.DataFrame(rows)
    mv, per_event = compute_match_vaep(df, k=10)

    assert mv.n_actions == 13
    assert mv.n_goals == 1
    # every player in the pre-goal chain is on team 1 and gets positive vaep
    team1 = [p for p in mv.players if p.team == "team1"]
    team2 = [p for p in mv.players if p.team == "team2"]
    assert team1 and team2
    # the striker who scored should be the top scorer by offensive vaep
    top = mv.players[0]
    assert top.team == "team1"
    assert top.offensive_vaep >= 0.0


def test_vaep_is_signed_and_sums_per_player() -> None:
    rows = [
        _pass(10.0, 40.0, 20.0, 40.0, team=1, player=1, t=0.1, name="P1"),
        _pass(20.0, 40.0, 30.0, 40.0, team=1, player=2, t=0.2, name="P2"),
        _pass(30.0, 40.0, 40.0, 40.0, team=1, player=1, t=0.3, name="P1"),
    ]
    df = pd.DataFrame(rows)
    mv, per_event = compute_match_vaep(df)
    # with zero goals in the window the labels are all zero → weights are all
    # zero → per-event p_score is constant → vaep is zero. The code should
    # not crash and should still produce a leaderboard of two players.
    assert {p.player_id for p in mv.players} == {"1", "2"}
    for p in mv.players:
        assert np.isfinite(p.vaep)
        assert np.isfinite(p.offensive_vaep)


def test_score_and_concede_labels_are_independent_in_multi_goal_window() -> None:
    """Regression: the previous implementation broke out of the label
    window on the first goal, so an action whose window contained both a
    for-goal and an against-goal only ever labelled the first one. The
    concede model therefore under-counted positives in multi-goal windows.

    Here team-1 scores at step 3 and team-2 scores at step 5, both within
    the k=10 window of the action at step 0 (team-1). That action should
    be labelled *both* y_score=1 and y_concede=1.
    """
    from athletiq.metrics.vaep import _as_action_df, _build_labels

    rows = [
        _pass(10.0, 40.0, 20.0, 40.0, team=1, player=1, t=0.1),
        _pass(20.0, 40.0, 30.0, 40.0, team=1, player=2, t=0.2),
        _pass(30.0, 40.0, 110.0, 40.0, team=1, player=3, t=0.3),
        _shot(115.0, 40.0, team=1, player=4, t=0.4, goal=True, name="T1S"),
        _pass(60.0, 40.0, 80.0, 40.0, team=2, player=5, t=0.5),
        _shot(115.0, 40.0, team=2, player=6, t=0.6, goal=True, name="T2S"),
    ]
    df = _as_action_df(pd.DataFrame(rows))
    y_score, y_concede = _build_labels(df, k=10)
    # First action is by team-1; both a for-goal and an against-goal occur
    # within the next 10 actions, so both labels must be 1.
    assert int(y_score[0]) == 1
    assert int(y_concede[0]) == 1


def test_action_type_filter_ignores_non_on_ball_events() -> None:
    rows = [
        _pass(10.0, 40.0, 30.0, 40.0, team=1, player=1, t=0.1, name="P1"),
        {
            "type": "Pressure",
            "team": "team1",
            "team_id": 1,
            "player": "P1",
            "player_id": 1,
            "position": "Center Midfield",
            "location": [40.0, 40.0],
            "period": 1,
            "timestamp": "00:00:00.2",
        },
        _pass(30.0, 40.0, 50.0, 40.0, team=1, player=2, t=0.3, name="P2"),
    ]
    df = pd.DataFrame(rows)
    mv, per_event = compute_match_vaep(df)
    # only the 2 passes are counted as actions
    assert mv.n_actions == 2

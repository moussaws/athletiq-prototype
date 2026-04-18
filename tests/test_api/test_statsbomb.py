"""Tests for the StatsBomb route and data adapter.

Heavy upstream calls to the StatsBomb CDN are mocked via monkeypatching
the module-level ``sb`` symbol on :mod:`athletiq.data.statsbomb`.  The
adapter's aggregation logic is exercised against a minimal fake events
DataFrame that mirrors real StatsBomb schema.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from athletiq.api.main import app
from athletiq.data import statsbomb as sb_mod


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ─── Fake statsbombpy facade ───────────────────────────────────────────
class _FakeSB:
    def competitions(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "competition_id": 43,
                    "season_id": 106,
                    "country_name": "International",
                    "competition_name": "FIFA World Cup",
                    "competition_gender": "male",
                    "competition_youth": False,
                    "competition_international": True,
                    "season_name": "2022",
                    "match_updated": "",
                    "match_updated_360": None,
                    "match_available_360": None,
                    "match_available": "",
                },
                {
                    "competition_id": 72,
                    "season_id": 107,
                    "country_name": "International",
                    "competition_name": "Women's World Cup",
                    "competition_gender": "female",
                    "competition_youth": False,
                    "competition_international": True,
                    "season_name": "2023",
                    "match_updated": "",
                    "match_updated_360": None,
                    "match_available_360": None,
                    "match_available": "",
                },
            ]
        )

    def matches(self, competition_id: int, season_id: int) -> pd.DataFrame:
        if competition_id == 43 and season_id == 106:
            return pd.DataFrame(
                [
                    {
                        "match_id": 3857286,
                        "match_date": "2022-11-20",
                        "home_team": "Qatar",
                        "away_team": "Ecuador",
                        "home_score": 0,
                        "away_score": 2,
                    }
                ]
            )
        return pd.DataFrame(
            columns=[
                "match_id",
                "match_date",
                "home_team",
                "away_team",
                "home_score",
                "away_score",
            ]
        )

    def events(self, match_id: int) -> pd.DataFrame:
        # Minimal schema that exercises all feature extractors.
        return pd.DataFrame(
            [
                # Qatar passes (5 completed, 1 incomplete)
                *[
                    {
                        "type": "Pass",
                        "player": "Hassan Al Haydos",
                        "player_id": 1001,
                        "position": "Center Midfield",
                        "team": "Qatar",
                        "team_id": 100,
                        "location": [50, 40],
                        "pass_outcome": None,
                    }
                    for _ in range(5)
                ],
                {
                    "type": "Pass",
                    "player": "Hassan Al Haydos",
                    "player_id": 1001,
                    "position": "Center Midfield",
                    "team": "Qatar",
                    "team_id": 100,
                    "location": [60, 40],
                    "pass_outcome": "Incomplete",
                },
                # Al Haydos carry 60→80 (progressive)
                {
                    "type": "Carry",
                    "player": "Hassan Al Haydos",
                    "player_id": 1001,
                    "position": "Center Midfield",
                    "team": "Qatar",
                    "team_id": 100,
                    "location": [60, 40],
                    "carry_end_location": [90, 40],
                    "pass_outcome": None,
                },
                # Al Haydos take-on
                {
                    "type": "Dribble",
                    "player": "Hassan Al Haydos",
                    "player_id": 1001,
                    "position": "Center Midfield",
                    "team": "Qatar",
                    "team_id": 100,
                    "location": [70, 40],
                    "pass_outcome": None,
                },
                # Ecuador defender: 2 interceptions, 1 tackle, 1 shot
                {
                    "type": "Interception",
                    "player": "Piero Hincapié",
                    "player_id": 2001,
                    "position": "Left Center Back",
                    "team": "Ecuador",
                    "team_id": 200,
                    "location": [30, 30],
                    "pass_outcome": None,
                },
                {
                    "type": "Interception",
                    "player": "Piero Hincapié",
                    "player_id": 2001,
                    "position": "Left Center Back",
                    "team": "Ecuador",
                    "team_id": 200,
                    "location": [25, 35],
                    "pass_outcome": None,
                },
                {
                    "type": "Duel",
                    "player": "Piero Hincapié",
                    "player_id": 2001,
                    "position": "Left Center Back",
                    "team": "Ecuador",
                    "team_id": 200,
                    "location": [20, 40],
                    "pass_outcome": None,
                },
                {
                    "type": "Shot",
                    "player": "Enner Valencia",
                    "player_id": 2002,
                    "position": "Center Forward",
                    "team": "Ecuador",
                    "team_id": 200,
                    "location": [100, 40],
                    "pass_outcome": None,
                },
            ]
        )


@pytest.fixture(autouse=True)
def _patch_sb(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Swap in the fake statsbombpy facade + clear the LRU cache."""
    monkeypatch.setattr(sb_mod, "sb", _FakeSB())
    monkeypatch.setattr(sb_mod, "STATSBOMB_AVAILABLE", True)
    sb_mod.clear_match_cache()
    yield
    sb_mod.clear_match_cache()


# ─── Adapter-level tests ───────────────────────────────────────────────
def test_list_competitions_returns_dataclasses() -> None:
    comps = sb_mod.list_competitions()
    assert len(comps) == 2
    assert comps[0].competition_name == "FIFA World Cup"
    assert comps[1].competition_gender == "female"


def test_list_matches_returns_dataclasses() -> None:
    ms = sb_mod.list_matches(43, 106)
    assert len(ms) == 1
    assert ms[0].match_id == 3857286
    assert ms[0].home_team == "Qatar"
    assert ms[0].away_score == 2


def test_load_match_players_aggregates_features() -> None:
    players = sb_mod.load_match_players(3857286)
    by_id = {p.player_id: p for p in players}
    assert "SB1001" in by_id
    assert "SB2001" in by_id
    assert "SB2002" in by_id

    hassan = by_id["SB1001"]
    assert hassan.position == "CM"
    assert hassan.nationality == "Qatar"
    assert hassan.features["passes_completed"] == 5.0
    assert hassan.features["take_ons"] == 1.0
    assert hassan.features["xt_carry"] > 0.0  # progressive carry 60→90

    hincapie = by_id["SB2001"]
    assert hincapie.position == "CB"
    assert hincapie.features["interceptions"] == 2.0
    assert hincapie.features["tackles"] == 1.0

    valencia = by_id["SB2002"]
    assert valencia.position == "ST"
    assert valencia.features["shots"] == 1.0


# ─── Route-level tests ─────────────────────────────────────────────────
def test_capabilities_available(client: TestClient) -> None:
    r = client.get("/api/statsbomb/capabilities")
    assert r.status_code == 200
    assert r.json()["statsbomb_available"] is True


def test_competitions_route(client: TestClient) -> None:
    r = client.get("/api/statsbomb/competitions")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert body["items"][0]["competition_name"] == "FIFA World Cup"


def test_matches_route(client: TestClient) -> None:
    r = client.get("/api/statsbomb/matches?competition_id=43&season_id=106")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["match_id"] == 3857286
    assert body["items"][0]["home_team"] == "Qatar"


def test_match_cohort_route(client: TestClient) -> None:
    r = client.get("/api/statsbomb/match/3857286")
    assert r.status_code == 200
    body = r.json()
    assert body["match_id"] == 3857286
    assert body["home_team"] == "Qatar"
    assert body["away_team"] == "Ecuador"
    assert body["score"] == "0-2"
    # 3 distinct players from the fake events
    assert len(body["players"]) == 3
    names = {p["name"] for p in body["players"]}
    assert names == {"Hassan Al Haydos", "Piero Hincapié", "Enner Valencia"}
    # Imputed feature list surfaced to the UI
    assert "pabr" in body["imputed_features"]
    assert "ddi" in body["imputed_features"]


def test_match_cohort_404_on_empty_events(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _EmptySB(_FakeSB):
        def events(self, match_id: int) -> pd.DataFrame:  # type: ignore[override]
            return pd.DataFrame()

    monkeypatch.setattr(sb_mod, "sb", _EmptySB())
    sb_mod.clear_match_cache()
    r = client.get("/api/statsbomb/match/999")
    assert r.status_code == 404

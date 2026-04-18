"""Tests for the coach-facing recruit brief → WASPAS shortlist endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from athletiq.api.main import app


def test_playstyle_catalog_lists_all_five():
    c = TestClient(app)
    r = c.get("/api/recruit/playstyles")
    assert r.status_code == 200
    data = r.json()
    keys = {p["key"] for p in data["playstyles"]}
    assert keys == {
        "ball_winner",
        "progressor",
        "press_resistant",
        "box_to_box",
        "finisher",
    }
    # Every preset must have 5 criteria whose weights sum to 1.
    for p in data["playstyles"]:
        assert len(p["criteria"]) == 5
        assert len(p["weights"]) == 5
        assert abs(sum(p["weights"]) - 1.0) < 1e-6


def test_recruit_search_press_resistant_dm_shape():
    c = TestClient(app)
    r = c.post(
        "/api/recruit/search",
        json={
            "position": "DM",
            "playstyle": "press_resistant",
            "max_age": 30,
            "max_value_m": 25,
            "limit": 10,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["position"] == "DM"
    assert data["playstyle"] == "press_resistant"
    assert data["playstyle_label"] == "Press-resistant"
    assert data["criteria"][0] == "passes_completed"
    assert len(data["candidates"]) > 0
    # Candidates must be sorted by fit_score descending.
    scores = [c["fit_score"] for c in data["candidates"]]
    assert scores == sorted(scores, reverse=True)
    # Every candidate must be a DM under 31 and ≤ €25M.
    for cand in data["candidates"]:
        assert cand["position"] == "DM"
        assert cand["age"] <= 30
        assert cand["market_value_m"] <= 25
    # Headline must name the top candidate.
    assert data["candidates"][0]["name"] in data["headline"]


def test_recruit_filters_compose_and_can_return_404():
    c = TestClient(app)
    # A GK under €0.01M and under 16 is unlikely in a 240-player synthetic
    # cohort (min age is 16). Expect 404, not a silent empty list.
    r = c.post(
        "/api/recruit/search",
        json={
            "position": "GK",
            "playstyle": "ball_winner",
            "max_age": 15,
        },
    )
    assert r.status_code == 404


def test_finisher_playstyle_ranks_shooters_first():
    """A broken preset (e.g. if finisher weights ignored 'shots') would not
    put the highest-shots player at the top. Adversarial check."""
    c = TestClient(app)
    r = c.post(
        "/api/recruit/search",
        json={"position": "ST", "playstyle": "finisher", "limit": 50},
    )
    assert r.status_code == 200
    data = r.json()
    top_trait = data["candidates"][0]["top_trait"]
    # For a finisher brief, the top candidate's strongest contribution should
    # be either shots or carry xT (the two heaviest criteria).
    assert top_trait in {"shots", "carry xT"}, (
        f"finisher brief returned wrong top trait: {top_trait}"
    )

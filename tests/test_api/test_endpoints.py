"""Smoke-test the FastAPI routes end-to-end against a live TestClient."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from athletiq.api.main import app
from athletiq.api.state import reset_store


@pytest.fixture(autouse=True)
def _fresh_state():
    reset_store()
    yield
    reset_store()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_list_players(client: TestClient) -> None:
    r = client.get("/api/players?limit=10")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] > 0
    assert len(body["items"]) == 10


def test_get_player(client: TestClient) -> None:
    lst = client.get("/api/players?limit=1").json()
    pid = lst["items"][0]["player_id"]
    r = client.get(f"/api/players/{pid}")
    assert r.status_code == 200
    assert r.json()["player_id"] == pid


def test_pressure_endpoint(client: TestClient) -> None:
    r = client.post(
        "/api/metrics/pressure",
        json={
            "defenders": [{"x": 1, "y": 0}, {"x": 10, "y": 0}],
            "carrier": {"x": 0, "y": 0},
            "radius": 5.0,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["raw_individual"][0] > 0
    assert body["raw_individual"][1] == 0.0
    assert body["collective"] > 0


def test_pabr_endpoint(client: TestClient) -> None:
    r = client.post(
        "/api/metrics/pabr",
        json={
            "sequences": [
                {"mean_pressure": 0.1, "retained": True},
                {"mean_pressure": 3.0, "retained": False},
            ]
        },
    )
    assert r.status_code == 200
    assert 0 <= r.json()["pabr"] <= 1


def test_pitch_control_demo(client: TestClient) -> None:
    r = client.get("/api/pitch-control/demo")
    assert r.status_code == 200
    body = r.json()
    assert len(body["phi"]) > 0
    assert len(body["phi"][0]) > 0


def test_ahp_and_squad(client: TestClient) -> None:
    ahp = client.post(
        "/api/squad/ahp",
        json={
            "criteria": ["pabr", "xt_carry", "interceptions"],
            "pairwise_matrix": [
                [1, 2, 3],
                [0.5, 1, 2],
                [1 / 3, 0.5, 1],
            ],
        },
    )
    assert ahp.status_code == 200
    weights = ahp.json()["weights"]
    assert ahp.json()["is_consistent"] is True

    squad = client.post(
        "/api/squad",
        json={
            "criteria": ["pabr", "xt_carry", "interceptions"],
            "weights": weights,
            "formation": {"GK": 1, "CB": 2, "FB": 2, "DM": 1, "CM": 2, "AM": 1, "WG": 1, "ST": 1},
            "budget": 800.0,
            "foreign_max": 6,
        },
    )
    assert squad.status_code == 200
    body = squad.json()
    assert len(body["assignments"]) == 11
    assert body["foreign_count"] <= 6
    assert body["budget_used"] <= 800.0


def test_similar_players(client: TestClient) -> None:
    pid = client.get("/api/players?limit=1").json()["items"][0]["player_id"]
    r = client.get(f"/api/scouting/similar/{pid}?k=5")
    assert r.status_code == 200
    assert len(r.json()["results"]) == 5


def test_archetypes(client: TestClient) -> None:
    r = client.get("/api/scouting/archetypes/CB")
    assert r.status_code == 200
    body = r.json()
    assert body["position"] == "CB"
    assert body["k"] >= 2


def test_cv_capabilities(client: TestClient) -> None:
    r = client.get("/api/cv/capabilities")
    assert r.status_code == 200
    # Doesn't assert cv_available — depends on whether [cv] extras are installed.
    assert "cv_available" in r.json()

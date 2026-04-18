"""Endpoint tests for persisted AHP preferences + saved squads."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from athletiq.api.main import app
from athletiq.db import init_db
from athletiq.db.session import reset_engine


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path):
    # File-based SQLite in tmp_path so every pool connection sees the same DB
    # (in-memory SQLite opens a fresh DB per connection).
    reset_engine(f"sqlite:///{tmp_path}/test.db")
    init_db()
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _pref_payload(name: str = "Pressing") -> dict:
    return {
        "name": name,
        "criteria": ["pabr", "ddi", "xt_carry"],
        "pairwise_matrix": [[1.0, 3.0, 5.0], [1 / 3, 1.0, 3.0], [0.2, 1 / 3, 1.0]],
        "weights": [0.637, 0.258, 0.105],
        "consistency_ratio": 0.03,
        "is_consistent": True,
    }


def test_create_list_get_preference(client: TestClient) -> None:
    created = client.post("/api/squad/preferences", json=_pref_payload()).json()
    assert created["id"] >= 1
    assert created["name"] == "Pressing"
    assert created["criteria"] == ["pabr", "ddi", "xt_carry"]
    assert created["weights"][0] == pytest.approx(0.637)

    listing = client.get("/api/squad/preferences").json()
    assert len(listing) == 1
    assert listing[0]["id"] == created["id"]

    fetched = client.get(f"/api/squad/preferences/{created['id']}").json()
    assert fetched == created


def test_delete_preference(client: TestClient) -> None:
    created = client.post("/api/squad/preferences", json=_pref_payload()).json()
    r = client.delete(f"/api/squad/preferences/{created['id']}")
    assert r.status_code == 204
    assert client.get(f"/api/squad/preferences/{created['id']}").status_code == 404


def test_preference_shape_validation(client: TestClient) -> None:
    bad = _pref_payload()
    bad["pairwise_matrix"] = [[1.0, 3.0], [1 / 3, 1.0]]  # 2x2 but 3 criteria
    r = client.post("/api/squad/preferences", json=bad)
    assert r.status_code == 422

    bad2 = _pref_payload()
    bad2["weights"] = [0.5, 0.5]  # length 2 but 3 criteria
    assert client.post("/api/squad/preferences", json=bad2).status_code == 422


def test_get_missing_preference_is_404(client: TestClient) -> None:
    assert client.get("/api/squad/preferences/999").status_code == 404
    assert client.delete("/api/squad/preferences/999").status_code == 404


def _squad_payload(preference_id: int | None = None, name: str = "XI-2026") -> dict:
    return {
        "name": name,
        "preference_id": preference_id,
        "criteria": ["pabr", "ddi"],
        "weights": [0.7, 0.3],
        "formation": {"GK": 1, "CB": 2, "FB": 2, "DM": 1, "CM": 2, "AM": 1, "WG": 1, "ST": 1},
        "budget": 800.0,
        "foreign_max": 6,
        "assignments": [
            {
                "position": "GK",
                "player_id": "p001",
                "name": "Keeper One",
                "nationality": "DZA",
                "age": 28,
                "market_value_m": 12.0,
                "is_foreign": False,
                "positional_fit": 0.91,
            }
        ],
        "total_score": 8.4,
        "squad_gap_position": "FB",
        "squad_gap_delta": 0.12,
        "budget_used": 650.0,
        "foreign_count": 4,
    }


def test_create_list_get_saved_squad(client: TestClient) -> None:
    pref = client.post("/api/squad/preferences", json=_pref_payload()).json()
    created = client.post("/api/squad/saved", json=_squad_payload(preference_id=pref["id"])).json()
    assert created["id"] >= 1
    assert created["preference_id"] == pref["id"]
    assert len(created["assignments"]) == 1
    assert created["assignments"][0]["name"] == "Keeper One"

    listing = client.get("/api/squad/saved").json()
    assert len(listing) == 1
    assert listing[0]["id"] == created["id"]


def test_saved_squad_rejects_missing_preference_fk(client: TestClient) -> None:
    r = client.post("/api/squad/saved", json=_squad_payload(preference_id=9999))
    assert r.status_code == 422


def test_saved_squad_with_null_preference_is_allowed(client: TestClient) -> None:
    r = client.post("/api/squad/saved", json=_squad_payload(preference_id=None))
    assert r.status_code == 201
    assert r.json()["preference_id"] is None


def test_delete_saved_squad(client: TestClient) -> None:
    created = client.post("/api/squad/saved", json=_squad_payload()).json()
    r = client.delete(f"/api/squad/saved/{created['id']}")
    assert r.status_code == 204
    assert client.get(f"/api/squad/saved/{created['id']}").status_code == 404


def test_empty_listings(client: TestClient) -> None:
    assert client.get("/api/squad/preferences").json() == []
    assert client.get("/api/squad/saved").json() == []


def test_ordering_is_newest_first(client: TestClient) -> None:
    ids = [
        client.post("/api/squad/preferences", json=_pref_payload(f"Pref-{i}")).json()["id"]
        for i in range(3)
    ]
    listing = client.get("/api/squad/preferences").json()
    assert [row["id"] for row in listing] == list(reversed(ids))

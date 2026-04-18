"""Paper §4.4.3 — Binary Integer Programming squad optimization (Eq. 14–18)."""

from __future__ import annotations

import numpy as np
import pytest

from athletiq.scouting.bip import optimize_squad


def _trivial_instance() -> dict:
    # 6 players, 3 positions, 3 slots.
    # GK candidate: P0; CB candidates: P1 (strong), P2; ST candidates: P3 (strong), P4, P5.
    Q = np.array(
        [
            [0.9, 0.0, 0.0],  # P0 -> GK
            [0.0, 0.8, 0.0],  # P1 -> CB
            [0.0, 0.4, 0.0],  # P2 -> CB
            [0.0, 0.0, 0.9],  # P3 -> ST
            [0.0, 0.0, 0.5],  # P4 -> ST
            [0.0, 0.0, 0.4],  # P5 -> ST
        ]
    )
    return {
        "Q": Q,
        "player_ids": [f"P{i}" for i in range(6)],
        "positions": ["GK", "CB", "ST"],
        "formation": {"GK": 1, "CB": 1, "ST": 1},
        "foreign_flags": [False] * 6,
        "market_values": [5.0] * 6,
        "budget": 1000.0,
        "foreign_max": 0,
    }


def _player_at(r, position: str) -> str:
    return next(pid for pid, pos in r.assignments.items() if pos == position)


def test_picks_optimal_under_free_budget() -> None:
    r = optimize_squad(**_trivial_instance())
    assert r.assignments == {"P0": "GK", "P1": "CB", "P3": "ST"}
    assert r.total_score == pytest.approx(2.6)


def test_budget_constraint_is_enforced() -> None:
    inst = _trivial_instance()
    inst["market_values"] = [1.0, 100.0, 1.0, 100.0, 1.0, 1.0]
    inst["budget"] = 5.0
    r = optimize_squad(**inst)
    # Must fall back to the cheap CB (P2) and a cheap ST (P4 or P5).
    assert _player_at(r, "CB") == "P2"
    assert _player_at(r, "ST") in {"P4", "P5"}
    assert r.budget_used <= 5.0


def test_foreign_quota_enforced() -> None:
    inst = _trivial_instance()
    # Strong CB and strong ST are foreigners; quota forces us to pick the domestic fallbacks.
    inst["foreign_flags"] = [False, True, False, True, False, False]
    inst["foreign_max"] = 1
    r = optimize_squad(**inst)
    assert r.foreign_count <= 1


def test_squad_gap_identifies_weakest_slot() -> None:
    inst = _trivial_instance()
    # Force CB to pick the weak candidate
    inst["market_values"] = [1.0, 100.0, 1.0, 1.0, 1.0, 1.0]
    inst["budget"] = 4.0  # just enough for 3 x 1 + tax for weak CB
    r = optimize_squad(**inst)
    # CB delta = 0.8 - 0.4 = 0.4 should be the largest gap
    assert r.squad_gap_position == "CB"
    assert r.squad_gap_delta == pytest.approx(0.4)


def test_formation_fully_covered() -> None:
    r = optimize_squad(**_trivial_instance())
    assert len(r.assignments) == 3


def test_positions_and_q_shape_must_match() -> None:
    inst = _trivial_instance()
    inst["positions"] = ["GK", "CB"]  # mismatch vs Q.shape[1]
    with pytest.raises(ValueError):
        optimize_squad(**inst)

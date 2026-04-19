"""Tactical Counterfactual Lab — scenario engine unit tests (PR 1)."""

from __future__ import annotations

import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from athletiq.api.main import app
from athletiq.data.synthetic import generate_synthetic_snapshot
from athletiq.metrics.pitch_control import pitch_control_surface
from athletiq.metrics.pitch_control_zones import zonal_summary
from athletiq.metrics.scenario import (
    VALID_FORMATIONS,
    default_ball_position,
    defensive_line_height_m,
    diff_scenarios,
    formation_preset,
    phi_from_positions,
)
from athletiq.metrics.types import PITCH_LENGTH_M

client = TestClient(app)


# ---------------------------------------------------------------------------
# phi_from_positions
# ---------------------------------------------------------------------------


def test_phi_from_positions_is_deterministic() -> None:
    atk = [(30, 30), (60, 34), (80, 40)]
    dfn = [(40, 30), (70, 34), (90, 40)]
    ball = (55, 34)
    phi1, xs1, ys1 = phi_from_positions(atk, dfn, ball, grid_shape=(34, 52))
    phi2, xs2, ys2 = phi_from_positions(atk, dfn, ball, grid_shape=(34, 52))
    assert np.array_equal(phi1, phi2)
    assert np.array_equal(xs1, xs2)
    assert np.array_equal(ys1, ys2)
    assert phi1.shape == (34, 52)
    assert xs1.shape == (52,)
    assert ys1.shape == (34,)


def test_phi_matches_pitch_control_surface() -> None:
    """`phi_from_positions` is a thin wrapper — must agree with the core API."""
    players = generate_synthetic_snapshot(seed=0)
    atk = [(p.x, p.y) for p in players if p.team == 0]
    dfn = [(p.x, p.y) for p in players if p.team == 1]
    atk_vel = np.array([[p.vx, p.vy] for p in players if p.team == 0])
    dfn_vel = np.array([[p.vx, p.vy] for p in players if p.team == 1])

    phi_a, _, _ = phi_from_positions(
        atk,
        dfn,
        ball=(52.5, 34),
        attacker_velocities=atk_vel,
        defender_velocities=dfn_vel,
        grid_shape=(34, 52),
    )
    phi_b, _, _ = pitch_control_surface(players, grid_shape=(34, 52))
    assert np.allclose(phi_a, phi_b, atol=1e-9)


def test_phi_increases_when_defender_retreats() -> None:
    """Monotonicity check — pulling the nearest defender off the attacker
    should never *decrease* attacker dominance in the region around the ball."""
    atk = [(60, 34)]
    dfn_close = [(62, 34)]
    dfn_far = [(90, 34)]
    phi_close, _, _ = phi_from_positions(atk, dfn_close, (60, 34), grid_shape=(34, 52))
    phi_far, _, _ = phi_from_positions(atk, dfn_far, (60, 34), grid_shape=(34, 52))
    assert phi_far.mean() > phi_close.mean()


def test_phi_rejects_bad_shapes() -> None:
    with pytest.raises(ValueError):
        phi_from_positions([], [(10, 10)], (50, 34))
    with pytest.raises(ValueError):
        phi_from_positions([(10, 10)], [], (50, 34))
    with pytest.raises(ValueError):
        # wrong-shape velocity array
        phi_from_positions(
            [(10, 10)],
            [(20, 20)],
            (50, 34),
            attacker_velocities=np.zeros((5, 2)),
        )


# ---------------------------------------------------------------------------
# defensive line height
# ---------------------------------------------------------------------------


def test_defensive_line_height_excludes_gk() -> None:
    # Defender (attacking-dir=+x): own goal at x=105, GK at x=98, back 4 at x=75
    defenders = [(98, 34), (75, 10), (75, 24), (75, 44), (75, 58)]
    # fill up to 11 with mids/forwards further up the pitch (smaller x)
    defenders += [(55, 14), (55, 28), (55, 40), (55, 54), (35, 24), (35, 44)]
    h = defensive_line_height_m(defenders)
    # GK at x=98 (largest x) is dropped; back 4 = x=75 x 4 → mean x = 75
    # line height = 105 - 75 = 30 m from own goal
    assert 28 <= h <= 32


def test_defensive_line_height_single_defender() -> None:
    """Regression: the single-defender case must still return distance from
    the defender's own goal, not raw x. Before the fix this fell through to a
    ``float(dfn[:, 0].mean())`` fallback in the API layer and returned ``90``
    for a lone defender at x=90 instead of the correct ``15``."""
    assert defensive_line_height_m([(90.0, 34.0)]) == pytest.approx(15.0)
    assert defensive_line_height_m([(0.0, 34.0)]) == pytest.approx(105.0)
    # two defenders, no GK to drop yet — still measured from own goal
    assert defensive_line_height_m([(80.0, 20.0), (80.0, 48.0)]) == pytest.approx(25.0)


def test_defensive_line_height_higher_means_pushed_up() -> None:
    # Deep block: defender GK at x=95, back line at x=85 → line height = 20 m
    deep = [(95, 34), (85, 10), (85, 30), (85, 50), (85, 65)]
    deep += [(65, 14), (65, 28), (65, 40), (65, 54), (50, 24), (50, 44)]
    # High press: defender GK at x=95, back line at x=60 → line height = 45 m
    high = [(95, 34), (60, 10), (60, 30), (60, 50), (60, 65)]
    high += [(45, 14), (45, 28), (45, 40), (45, 54), (30, 24), (30, 44)]
    assert defensive_line_height_m(high) > defensive_line_height_m(deep)


# ---------------------------------------------------------------------------
# formation presets
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("formation", VALID_FORMATIONS)
@pytest.mark.parametrize("role", ["attacker", "defender"])
def test_every_preset_is_on_pitch_and_has_eleven_players(formation: str, role: str) -> None:
    positions = formation_preset(formation, role)  # type: ignore[arg-type]
    assert len(positions) == 11
    for x, y in positions:
        assert 0.0 <= x <= 105.0, f"{formation} {role}: x={x} off pitch"
        assert 0.0 <= y <= 68.0, f"{formation} {role}: y={y} off pitch"


def test_defender_preset_is_mirror_of_attacker() -> None:
    for f in VALID_FORMATIONS:
        atk = formation_preset(f, "attacker")
        dfn = formation_preset(f, "defender")
        for (ax, ay), (dx, dy) in zip(atk, dfn, strict=True):
            assert dx == pytest.approx(105.0 - ax)
            assert dy == pytest.approx(ay)


def test_unknown_formation_raises() -> None:
    with pytest.raises(ValueError):
        formation_preset("5-3-2", "attacker")
    with pytest.raises(ValueError):
        formation_preset("4-3-3", "goalie")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# scenario diff
# ---------------------------------------------------------------------------


def _snapshot_to_phi(players) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    phi, xx, yy = pitch_control_surface(players, grid_shape=(34, 52))
    return phi, xx[0], yy[:, 0]


def test_diff_identical_scenarios_is_zero() -> None:
    players = generate_synthetic_snapshot(seed=0)
    phi, xs, _ = _snapshot_to_phi(players)
    base = zonal_summary(phi, xs, np.linspace(0.5, 67.5, 34))
    dfn = np.array([[p.x, p.y] for p in players if p.team == 1])
    d = diff_scenarios(
        baseline=base,
        scenario=base,
        baseline_phi=phi,
        scenario_phi=phi,
        baseline_xs=xs,
        scenario_xs=xs,
        baseline_defenders=dfn,
        scenario_defenders=dfn,
    )
    assert d.delta_phi_mean == pytest.approx(0.0, abs=1e-12)
    assert d.delta_phi_final_third == pytest.approx(0.0, abs=1e-12)
    assert d.delta_balance_attacker_pct == pytest.approx(0.0, abs=1e-12)
    assert d.delta_defensive_line_height_m == pytest.approx(0.0, abs=1e-12)
    assert all(abs(v) < 1e-12 for v in d.per_zone_delta)
    assert "within noise" in d.headline.lower()


def test_diff_high_press_gives_space_in_behind() -> None:
    """Push the defender's whole block 10 m toward the attacker's own goal
    (a high press). We expect:

    * defensive line height INCREASES (line further from own goal),
    * attacker's final-third Φ INCREASES (defenders vacate the attacking
      third — classic "space in behind a high line"),
    * headline mentions the line push.
    """
    players = generate_synthetic_snapshot(seed=0)
    baseline_atk = [(p.x, p.y) for p in players if p.team == 0]
    baseline_dfn = [(p.x, p.y) for p in players if p.team == 1]

    scenario_dfn = [(max(x - 10.0, 0.0), y) for (x, y) in baseline_dfn]

    base_phi, base_xs, _ = phi_from_positions(
        baseline_atk, baseline_dfn, default_ball_position(), grid_shape=(34, 52)
    )
    scen_phi, scen_xs, _ = phi_from_positions(
        baseline_atk, scenario_dfn, default_ball_position(), grid_shape=(34, 52)
    )
    base_sum = zonal_summary(base_phi, base_xs, np.linspace(0.5, 67.5, 34))
    scen_sum = zonal_summary(scen_phi, scen_xs, np.linspace(0.5, 67.5, 34))

    d = diff_scenarios(
        baseline=base_sum,
        scenario=scen_sum,
        baseline_phi=base_phi,
        scenario_phi=scen_phi,
        baseline_xs=base_xs,
        scenario_xs=scen_xs,
        baseline_defenders=baseline_dfn,
        scenario_defenders=scenario_dfn,
    )
    assert d.delta_defensive_line_height_m == pytest.approx(10.0, abs=0.1)
    assert d.delta_phi_final_third > 0  # space in behind the high line
    assert "pushed up" in d.headline.lower()


def test_diff_deep_block_loses_final_third_dominance() -> None:
    """Drop the defender's whole block 10 m (deep block). We expect:

    * defensive line height DECREASES (closer to own goal),
    * attacker's final-third Φ DECREASES (defenders clog the attacking third).
    """
    players = generate_synthetic_snapshot(seed=0)
    baseline_atk = [(p.x, p.y) for p in players if p.team == 0]
    baseline_dfn = [(p.x, p.y) for p in players if p.team == 1]

    scenario_dfn = [(min(x + 10.0, PITCH_LENGTH_M), y) for (x, y) in baseline_dfn]

    base_phi, base_xs, _ = phi_from_positions(
        baseline_atk, baseline_dfn, default_ball_position(), grid_shape=(34, 52)
    )
    scen_phi, scen_xs, _ = phi_from_positions(
        baseline_atk, scenario_dfn, default_ball_position(), grid_shape=(34, 52)
    )
    base_sum = zonal_summary(base_phi, base_xs, np.linspace(0.5, 67.5, 34))
    scen_sum = zonal_summary(scen_phi, scen_xs, np.linspace(0.5, 67.5, 34))

    d = diff_scenarios(
        baseline=base_sum,
        scenario=scen_sum,
        baseline_phi=base_phi,
        scenario_phi=scen_phi,
        baseline_xs=base_xs,
        scenario_xs=scen_xs,
        baseline_defenders=baseline_dfn,
        scenario_defenders=scenario_dfn,
    )
    assert d.delta_defensive_line_height_m < 0
    assert d.delta_phi_final_third < 0
    assert "dropped back" in d.headline.lower()


def test_diff_rejects_grid_mismatch() -> None:
    a = np.full((34, 52), 0.5)
    b = np.full((10, 20), 0.5)
    xs_a = np.linspace(0.5, 104.5, 52)
    ys_a = np.linspace(0.5, 67.5, 34)
    xs_b = np.linspace(0.5, 104.5, 20)
    ys_b = np.linspace(0.5, 67.5, 10)
    zs_a = zonal_summary(a, xs_a, ys_a)
    zs_b = zonal_summary(b, xs_b, ys_b)
    with pytest.raises(ValueError, match="grid shape"):
        diff_scenarios(
            baseline=zs_a,
            scenario=zs_b,
            baseline_phi=a,
            scenario_phi=b,
            baseline_xs=xs_a,
            scenario_xs=xs_b,
            baseline_defenders=[(90, 34)],
            scenario_defenders=[(90, 34)],
        )


# ---------------------------------------------------------------------------
# performance
# ---------------------------------------------------------------------------


def test_phi_recompute_is_under_budget() -> None:
    """Φ for a 34x52 grid must recompute in <100 ms on CI — real UX target."""
    atk = [(x, y) for x in (20, 35, 50, 65, 80) for y in (17, 34, 51)][:11]
    dfn = [(x, y) for x in (25, 40, 55, 70, 85) for y in (20, 34, 48)][:11]
    # warm up
    phi_from_positions(atk, dfn, (55, 34), grid_shape=(34, 52))

    t0 = time.perf_counter()
    for _ in range(5):
        phi_from_positions(atk, dfn, (55, 34), grid_shape=(34, 52))
    elapsed_ms = (time.perf_counter() - t0) * 1000.0 / 5.0
    assert elapsed_ms < 100.0, f"Φ recompute took {elapsed_ms:.1f} ms (budget: 100 ms)"


# ---------------------------------------------------------------------------
# /api/pitch-control/scenario
# ---------------------------------------------------------------------------


def _scenario_payload(**overrides):
    atk = formation_preset("4-3-3", "attacker")
    dfn = formation_preset("4-3-3", "defender")
    payload = {
        "attackers": [{"x": x, "y": y} for (x, y) in atk],
        "defenders": [{"x": x, "y": y} for (x, y) in dfn],
        "ball": {"x": 52.5, "y": 34.0},
    }
    payload.update(overrides)
    return payload


def test_scenario_endpoint_returns_zonal_summary() -> None:
    r = client.post("/api/pitch-control/scenario", json=_scenario_payload())
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["phi"]) == 34
    assert len(body["phi"][0]) == 52
    assert body["zonal"] is not None
    assert len(body["zonal"]["zones"]) == 12
    assert body["diff"] is None  # no baseline_seed requested
    assert 0.0 <= body["defensive_line_height_m"] <= 105.0


def test_scenario_endpoint_returns_diff_when_baseline_seed_set() -> None:
    r = client.post(
        "/api/pitch-control/scenario",
        json=_scenario_payload(baseline_seed=0),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["diff"] is not None
    diff = body["diff"]
    assert "delta_phi_mean" in diff
    assert "delta_phi_final_third" in diff
    assert "delta_balance_attacker_pct" in diff
    assert "delta_defensive_line_height_m" in diff
    assert len(diff["per_zone_delta"]) == 12
    assert isinstance(diff["headline"], str) and diff["headline"]


def test_scenario_endpoint_validates_inputs() -> None:
    # empty attacker list
    r = client.post(
        "/api/pitch-control/scenario",
        json={
            "attackers": [],
            "defenders": [{"x": 50, "y": 34}],
            "ball": {"x": 50, "y": 34},
        },
    )
    assert r.status_code == 422
    # >11 defenders
    r = client.post(
        "/api/pitch-control/scenario",
        json={
            "attackers": [{"x": 50, "y": 34}],
            "defenders": [{"x": float(i), "y": 34.0} for i in range(12)],
            "ball": {"x": 50, "y": 34},
        },
    )
    assert r.status_code == 422


def test_scenario_endpoint_small_grid_skips_zonal_and_diff() -> None:
    r = client.post(
        "/api/pitch-control/scenario",
        json=_scenario_payload(grid_rows=3, grid_cols=52, baseline_seed=0),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["zonal"] is None
    assert body["diff"] is None


# ---------------------------------------------------------------------------
# /api/pitch-control/scenario/preset
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("formation", VALID_FORMATIONS)
@pytest.mark.parametrize("role", ["attacker", "defender"])
def test_preset_endpoint_returns_eleven_on_pitch_positions(formation: str, role: str) -> None:
    r = client.get(
        "/api/pitch-control/scenario/preset",
        params={"formation": formation, "role": role},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["formation"] == formation
    assert body["role"] == role
    assert len(body["positions"]) == 11
    assert sorted(body["valid_formations"]) == sorted(VALID_FORMATIONS)
    for p in body["positions"]:
        assert 0.0 <= p["x"] <= 105.0
        assert 0.0 <= p["y"] <= 68.0
    assert 0.0 <= body["ball"]["x"] <= 105.0
    assert 0.0 <= body["ball"]["y"] <= 68.0


def test_preset_endpoint_rejects_unknown_formation() -> None:
    r = client.get(
        "/api/pitch-control/scenario/preset",
        params={"formation": "5-3-2", "role": "attacker"},
    )
    assert r.status_code == 422


def test_preset_then_scenario_round_trip() -> None:
    """Fetch a preset and feed it straight into /scenario — must succeed."""
    atk = client.get(
        "/api/pitch-control/scenario/preset",
        params={"formation": "4-4-2", "role": "attacker"},
    ).json()
    dfn = client.get(
        "/api/pitch-control/scenario/preset",
        params={"formation": "4-4-2", "role": "defender"},
    ).json()
    r = client.post(
        "/api/pitch-control/scenario",
        json={
            "attackers": atk["positions"],
            "defenders": dfn["positions"],
            "ball": atk["ball"],
            "baseline_seed": 0,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["zonal"] is not None
    assert body["diff"] is not None


def test_scenario_endpoint_accepts_explicit_baseline() -> None:
    """Lab workflow: coach captures the formation preset as baseline, then
    pushes edited positions and the server returns the delta against that
    explicit baseline rather than a seeded demo snapshot."""
    atk = client.get(
        "/api/pitch-control/scenario/preset",
        params={"formation": "4-3-3", "role": "attacker"},
    ).json()
    dfn = client.get(
        "/api/pitch-control/scenario/preset",
        params={"formation": "4-3-3", "role": "defender"},
    ).json()
    baseline = {
        "attackers": atk["positions"],
        "defenders": dfn["positions"],
        "ball": atk["ball"],
    }
    # Current = baseline with every defender pushed 10 m back toward own goal.
    current_defenders = [{"x": max(0.0, p["x"] - 10.0), "y": p["y"]} for p in dfn["positions"]]
    r = client.post(
        "/api/pitch-control/scenario",
        json={
            "attackers": atk["positions"],
            "defenders": current_defenders,
            "ball": atk["ball"],
            "baseline": baseline,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["diff"] is not None
    diff = body["diff"]
    # Pushing the defensive line 10 m deeper must *increase* the line height
    # relative to baseline (higher number = press higher = farther from own goal).
    assert diff["delta_defensive_line_height_m"] == pytest.approx(10.0, abs=0.5)
    # Headline should be non-empty, human-readable, and reflect the change.
    assert isinstance(diff["headline"], str) and diff["headline"].strip()


def test_scenario_endpoint_baseline_overrides_baseline_seed() -> None:
    """If both ``baseline`` and ``baseline_seed`` are supplied, the explicit
    ``baseline`` wins (documented in the field description)."""
    preset = client.get(
        "/api/pitch-control/scenario/preset",
        params={"formation": "4-3-3", "role": "attacker"},
    ).json()
    dfn_preset = client.get(
        "/api/pitch-control/scenario/preset",
        params={"formation": "4-3-3", "role": "defender"},
    ).json()
    baseline = {
        "attackers": preset["positions"],
        "defenders": dfn_preset["positions"],
        "ball": preset["ball"],
    }
    # Diff of the preset against itself: every delta must be ~0.
    r = client.post(
        "/api/pitch-control/scenario",
        json={
            "attackers": preset["positions"],
            "defenders": dfn_preset["positions"],
            "ball": preset["ball"],
            "baseline": baseline,
            "baseline_seed": 0,  # would produce non-zero deltas if honored
        },
    )
    assert r.status_code == 200
    diff = r.json()["diff"]
    assert diff is not None
    assert diff["delta_phi_mean"] == pytest.approx(0.0, abs=1e-6)
    assert diff["delta_defensive_line_height_m"] == pytest.approx(0.0, abs=1e-6)
    assert diff["delta_balance_attacker_pct"] == pytest.approx(0.0, abs=1e-6)

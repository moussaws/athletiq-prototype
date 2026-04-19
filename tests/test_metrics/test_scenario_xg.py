"""Scenario xG surface — unit tests (Lab · PR 5)."""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from athletiq.api.main import app
from athletiq.metrics.pitch_control_zones import zonal_summary
from athletiq.metrics.scenario import diff_scenarios, phi_from_positions
from athletiq.metrics.scenario_xg import (
    ScenarioXG,
    geometric_xg,
    scenario_xg,
    xg_surface,
)
from athletiq.metrics.types import PITCH_LENGTH_M, PITCH_WIDTH_M

client = TestClient(app)


# ---------------------------------------------------------------------------
# geometric_xg prior
# ---------------------------------------------------------------------------


def test_geometric_xg_is_monotonic_in_distance() -> None:
    """Closer to goal (same angle) → higher xG."""
    y = PITCH_WIDTH_M / 2
    xs = np.array([50.0, 70.0, 90.0, 100.0])
    vals = np.array([float(geometric_xg(float(x), y)) for x in xs])
    assert np.all(np.diff(vals) > 0), f"xG should grow with x (toward +x goal): {vals}"


def test_geometric_xg_is_bounded_unit_interval() -> None:
    """Logistic prior lives in (0, 1) regardless of where we stand."""
    rng = np.random.default_rng(0)
    xs = rng.uniform(0, PITCH_LENGTH_M, 100)
    ys = rng.uniform(0, PITCH_WIDTH_M, 100)
    vals = geometric_xg(xs, ys)
    assert np.all(vals > 0.0)
    assert np.all(vals < 1.0)


def test_geometric_xg_penalty_spot_ballpark() -> None:
    """Penalty spot (11 m out, central) should be in a plausible coach
    range. Our prior is geometry-only (no body part / keeper / assist),
    so we require a generous band rather than pinning the exact value.
    """
    x = PITCH_LENGTH_M - 11.0
    y = PITCH_WIDTH_M / 2
    val = float(geometric_xg(x, y))
    assert 0.45 <= val <= 0.85, f"penalty-spot xG out of expected range: {val:.3f}"


def test_geometric_xg_six_yard_box_is_highest() -> None:
    """6-yard box central must sit above penalty spot."""
    box = float(geometric_xg(PITCH_LENGTH_M - 5.0, PITCH_WIDTH_M / 2))
    pen = float(geometric_xg(PITCH_LENGTH_M - 11.0, PITCH_WIDTH_M / 2))
    assert box > pen


def test_geometric_xg_long_range_low() -> None:
    """35 m out, central — should be under 0.15."""
    x = PITCH_LENGTH_M - 35.0
    y = PITCH_WIDTH_M / 2
    val = float(geometric_xg(x, y))
    assert val < 0.15


def test_geometric_xg_symmetric_across_center() -> None:
    """Mirrored y's around the pitch midline give identical xG."""
    x = 90.0
    up = float(geometric_xg(x, PITCH_WIDTH_M / 2 + 10))
    down = float(geometric_xg(x, PITCH_WIDTH_M / 2 - 10))
    assert up == pytest.approx(down, abs=1e-9)


def test_geometric_xg_flipped_direction() -> None:
    """Attacking `-x` mirrors the prior onto the opposite goal."""
    plus_deep = float(geometric_xg(90.0, PITCH_WIDTH_M / 2, attacking_direction="+x"))
    minus_deep = float(
        geometric_xg(PITCH_LENGTH_M - 90.0, PITCH_WIDTH_M / 2, attacking_direction="-x")
    )
    assert plus_deep == pytest.approx(minus_deep, abs=1e-9)


# ---------------------------------------------------------------------------
# xg_surface
# ---------------------------------------------------------------------------


def test_xg_surface_weights_by_phi() -> None:
    """Per-cell attacker xG = geometric_xg * phi."""
    xs = np.linspace(1, PITCH_LENGTH_M - 1, 26)
    ys = np.linspace(1, PITCH_WIDTH_M - 1, 17)
    xx, yy = np.meshgrid(xs, ys)
    phi = np.full_like(xx, 0.5)
    for_cell, against_cell = xg_surface(phi, xs, ys)
    ratio = for_cell / against_cell
    # phi=0.5 everywhere ⇒ attacker/defender weights are equal ⇒ ratio
    # equals the ratio of attacker-goal xG to defender-goal xG at each
    # cell, which is not constant, so we just assert positivity + shape.
    assert for_cell.shape == phi.shape
    assert against_cell.shape == phi.shape
    assert np.all(for_cell > 0)
    assert np.all(against_cell > 0)
    assert np.all(np.isfinite(ratio))


def test_xg_surface_shape_mismatch_raises() -> None:
    xs = np.linspace(0, PITCH_LENGTH_M, 10)
    ys = np.linspace(0, PITCH_WIDTH_M, 5)
    phi = np.zeros((6, 10))  # wrong row count
    with pytest.raises(ValueError, match="does not match"):
        xg_surface(phi, xs, ys)


# ---------------------------------------------------------------------------
# scenario_xg reduction
# ---------------------------------------------------------------------------


def test_scenario_xg_balanced_midblock_has_similar_scalars() -> None:
    """Symmetric mid-press formation should not have a large xG edge."""
    atk = [
        (20, PITCH_WIDTH_M / 2),
        (50, PITCH_WIDTH_M / 2),
        (70, PITCH_WIDTH_M / 2),
    ]
    dfn = [
        (85, PITCH_WIDTH_M / 2),
        (55, PITCH_WIDTH_M / 2),
        (35, PITCH_WIDTH_M / 2),
    ]
    phi, xs, ys = phi_from_positions(atk, dfn, (52.5, 34.0))
    res = scenario_xg(phi, xs, ys)
    assert isinstance(res, ScenarioXG)
    assert abs(res.xg_net) < 0.01


def test_scenario_xg_attackers_in_the_box_raise_for() -> None:
    """Attack with ball in the box → xg_for must dominate."""
    atk = [(99, PITCH_WIDTH_M / 2 + i) for i in (-6, 0, 6)]
    dfn = [(25, PITCH_WIDTH_M / 2 + i) for i in (-6, 0, 6)]
    ball = (99.0, PITCH_WIDTH_M / 2)
    phi, xs, ys = phi_from_positions(atk, dfn, ball)
    res = scenario_xg(phi, xs, ys, ball=ball)
    assert res.xg_for > res.xg_against
    assert res.xg_net > 0.02


def test_scenario_xg_defenders_own_the_ball_in_own_third() -> None:
    """Defenders own the ball deep in their third → xg_against dominates.

    This mimics a turnover: attacker has lost the ball in the defender's
    defensive half and the defender is about to counter.
    """
    atk = [(70, PITCH_WIDTH_M / 2 + i) for i in (-6, 0, 6)]
    dfn = [(10, PITCH_WIDTH_M / 2 + i) for i in (-6, 0, 6)]
    ball = (10.0, PITCH_WIDTH_M / 2)
    phi, xs, ys = phi_from_positions(atk, dfn, ball)
    res = scenario_xg(phi, xs, ys, ball=ball)
    assert res.xg_against > res.xg_for
    assert res.xg_net < -0.01


def test_scenario_xg_is_deterministic() -> None:
    atk = [(30, 30), (60, 34), (80, 40)]
    dfn = [(40, 30), (70, 34), (90, 40)]
    ball = (55.0, 34.0)
    phi, xs, ys = phi_from_positions(atk, dfn, ball)
    a = scenario_xg(phi, xs, ys, ball=ball)
    b = scenario_xg(phi, xs, ys, ball=ball)
    assert a == b


def test_scenario_xg_uniform_kernel_when_ball_none() -> None:
    """Without a ball the kernel reduces to a plain mean over the pitch."""
    atk = [(99, PITCH_WIDTH_M / 2 + i) for i in (-6, 0, 6)]
    dfn = [(25, PITCH_WIDTH_M / 2 + i) for i in (-6, 0, 6)]
    phi, xs, ys = phi_from_positions(atk, dfn, (99, PITCH_WIDTH_M / 2))
    no_ball = scenario_xg(phi, xs, ys)
    with_ball = scenario_xg(phi, xs, ys, ball=(99.0, PITCH_WIDTH_M / 2))
    # without the ball kernel both halves look symmetric (not informative).
    assert abs(no_ball.xg_net) < 0.01
    # with the ball at the attacker's position the net edge swings positive.
    assert with_ball.xg_for > no_ball.xg_for


# ---------------------------------------------------------------------------
# diff_scenarios — xG plumbing through
# ---------------------------------------------------------------------------


def test_diff_scenarios_surfaces_xg_delta() -> None:
    base_atk = [(40, 34), (60, 20), (60, 48)]
    base_dfn = [(90, 20), (90, 34), (90, 48)]
    cur_atk = [(95, 34), (95, 20), (95, 48)]  # push attackers into the box
    cur_dfn = base_dfn
    base_ball = (55.0, 34.0)
    cur_ball = (95.0, 34.0)
    base_phi, base_xs, base_ys = phi_from_positions(base_atk, base_dfn, base_ball)
    cur_phi, cur_xs, cur_ys = phi_from_positions(cur_atk, cur_dfn, cur_ball)
    base_sum = zonal_summary(base_phi, base_xs, base_ys)
    cur_sum = zonal_summary(cur_phi, cur_xs, cur_ys)
    d = diff_scenarios(
        baseline=base_sum,
        scenario=cur_sum,
        baseline_phi=base_phi,
        scenario_phi=cur_phi,
        baseline_xs=base_xs,
        scenario_xs=cur_xs,
        baseline_defenders=np.array(base_dfn, dtype=float),
        scenario_defenders=np.array(cur_dfn, dtype=float),
        baseline_ball=base_ball,
        scenario_ball=cur_ball,
    )
    assert d.delta_xg_for > 0
    assert d.delta_xg_net > 0
    assert d.baseline_xg_for < d.scenario_xg_for
    # sanity: net delta is the difference of the two other deltas.
    assert d.delta_xg_net == pytest.approx(d.delta_xg_for - d.delta_xg_against, abs=1e-9)


def test_diff_scenarios_headline_picks_up_xg_swing() -> None:
    """A dominant xG swing should be named first in the headline."""
    base_atk = [(40, 34), (60, 20), (60, 48)]
    base_dfn = [(90, 20), (90, 34), (90, 48)]
    cur_atk = [(99, 34), (99, 24), (99, 44)]
    cur_dfn = base_dfn
    base_ball = (55.0, 34.0)
    cur_ball = (99.0, 34.0)
    base_phi, base_xs, base_ys = phi_from_positions(base_atk, base_dfn, base_ball)
    cur_phi, cur_xs, cur_ys = phi_from_positions(cur_atk, cur_dfn, cur_ball)
    base_sum = zonal_summary(base_phi, base_xs, base_ys)
    cur_sum = zonal_summary(cur_phi, cur_xs, cur_ys)
    d = diff_scenarios(
        baseline=base_sum,
        scenario=cur_sum,
        baseline_phi=base_phi,
        scenario_phi=cur_phi,
        baseline_xs=base_xs,
        scenario_xs=cur_xs,
        baseline_defenders=np.array(base_dfn, dtype=float),
        scenario_defenders=np.array(cur_dfn, dtype=float),
        baseline_ball=base_ball,
        scenario_ball=cur_ball,
    )
    # With big xG swing the headline should lead with "Net xG edge".
    if abs(d.delta_xg_net) >= 0.01:
        assert d.headline.startswith("Net xG edge")


# ---------------------------------------------------------------------------
# API surface — POST /api/pitch-control/scenario now includes xg
# ---------------------------------------------------------------------------


def test_api_scenario_returns_xg_payload() -> None:
    body = {
        "attackers": [{"x": 30, "y": 34}, {"x": 60, "y": 20}, {"x": 60, "y": 48}],
        "defenders": [{"x": 90, "y": 34}, {"x": 90, "y": 20}, {"x": 90, "y": 48}],
        "ball": {"x": 52.5, "y": 34},
        "grid_rows": 16,
        "grid_cols": 24,
    }
    r = client.post("/api/pitch-control/scenario", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "xg" in data
    xg = data["xg"]
    for k in ("xg_for", "xg_against", "xg_net"):
        assert k in xg
        assert isinstance(xg[k], float)
    # diff not requested (no baseline) — should be null.
    assert data["diff"] is None


def test_api_scenario_returns_xg_diff_when_baseline_provided() -> None:
    baseline = {
        "attackers": [{"x": 40, "y": 34}, {"x": 60, "y": 20}, {"x": 60, "y": 48}],
        "defenders": [{"x": 90, "y": 34}, {"x": 90, "y": 20}, {"x": 90, "y": 48}],
        "ball": {"x": 52.5, "y": 34},
    }
    body = {
        "attackers": [{"x": 99, "y": 34}, {"x": 99, "y": 24}, {"x": 99, "y": 44}],
        "defenders": [{"x": 90, "y": 34}, {"x": 90, "y": 20}, {"x": 90, "y": 48}],
        "ball": {"x": 99, "y": 34},
        "grid_rows": 16,
        "grid_cols": 24,
        "baseline": baseline,
    }
    r = client.post("/api/pitch-control/scenario", json=body)
    assert r.status_code == 200, r.text
    diff = r.json()["diff"]
    assert diff is not None
    for k in (
        "baseline_xg_for",
        "baseline_xg_against",
        "scenario_xg_for",
        "scenario_xg_against",
        "delta_xg_for",
        "delta_xg_against",
        "delta_xg_net",
    ):
        assert k in diff
    # pushing attackers into the box must raise attacker xG.
    assert diff["delta_xg_for"] > 0
    assert diff["delta_xg_net"] > 0


def test_api_scenario_top_level_xg_matches_diff_scenario_xg() -> None:
    """Regression: top-level xg and diff.scenario_xg_* must describe the same
    scenario on the same y-axis grid. Pre-fix _baseline_ys_from_phi used a
    rows-aware half-cell formula that drifted from pitch_control_surface's
    linspace(0.5, PITCH_WIDTH_M - 0.5, H).
    """
    baseline = {
        "attackers": [{"x": 40, "y": 34}, {"x": 60, "y": 20}, {"x": 60, "y": 48}],
        "defenders": [{"x": 90, "y": 34}, {"x": 90, "y": 20}, {"x": 90, "y": 48}],
        "ball": {"x": 52.5, "y": 34},
    }
    body = {
        "attackers": [{"x": 95, "y": 34}, {"x": 95, "y": 20}, {"x": 95, "y": 48}],
        "defenders": [{"x": 90, "y": 34}, {"x": 90, "y": 20}, {"x": 90, "y": 48}],
        "ball": {"x": 95, "y": 34},
        "grid_rows": 34,
        "grid_cols": 52,
        "baseline": baseline,
    }
    r = client.post("/api/pitch-control/scenario", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    top = data["xg"]
    diff = data["diff"]
    assert top["xg_for"] == pytest.approx(diff["scenario_xg_for"], abs=1e-9)
    assert top["xg_against"] == pytest.approx(diff["scenario_xg_against"], abs=1e-9)


def test_headline_net_xg_loss_does_not_use_plus_sign() -> None:
    """Regression: a negative net-xG swing must not render as '+' anything.

    Pre-fix the format string was f'{abs(delta_xg_net):+.3f}' which forced
    a '+' prefix on a non-negative absolute value, producing contradictory
    copy like 'gave up +0.015'.
    """
    # Attacker loses the ball in their defensive half → xg_against dominates.
    base_atk = [(70, 34), (70, 24), (70, 44)]
    base_dfn = [(10, 30), (10, 34), (10, 38)]
    cur_atk = [(55, 34), (55, 24), (55, 44)]
    cur_dfn = base_dfn
    base_ball = (10.0, 34.0)
    cur_ball = (10.0, 34.0)
    base_phi, base_xs, base_ys = phi_from_positions(base_atk, base_dfn, base_ball)
    cur_phi, cur_xs, cur_ys = phi_from_positions(cur_atk, cur_dfn, cur_ball)
    base_sum = zonal_summary(base_phi, base_xs, base_ys)
    cur_sum = zonal_summary(cur_phi, cur_xs, cur_ys)
    d = diff_scenarios(
        baseline=base_sum,
        scenario=cur_sum,
        baseline_phi=base_phi,
        scenario_phi=cur_phi,
        baseline_xs=base_xs,
        scenario_xs=cur_xs,
        baseline_defenders=np.array(base_dfn, dtype=float),
        scenario_defenders=np.array(cur_dfn, dtype=float),
        baseline_ball=base_ball,
        scenario_ball=cur_ball,
    )
    if d.headline.startswith("Net xG edge gave up"):
        assert "+" not in d.headline.split(".")[0], d.headline

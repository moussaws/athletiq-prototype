"""Zonal summary of a pitch-control surface (coach-facing read)."""

from __future__ import annotations

import numpy as np
import pytest

from athletiq.data.synthetic import generate_synthetic_snapshot
from athletiq.metrics.pitch_control import pitch_control_surface
from athletiq.metrics.pitch_control_zones import zonal_summary


def _xs_ys(phi_shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    h, w = phi_shape
    xs = np.linspace(0.5, 104.5, w)
    ys = np.linspace(0.5, 67.5, h)
    return xs, ys


def test_small_grid_raises_value_error() -> None:
    # grid smaller than (n_channels=4, n_thirds=3) cannot be zonally aggregated
    phi = np.full((3, 52), 0.5)
    xs, ys = _xs_ys(phi.shape)
    with pytest.raises(ValueError, match="too small"):
        zonal_summary(phi, xs, ys)


def test_post_endpoint_skips_zonal_for_small_grid() -> None:
    # POST /api/pitch-control used to 500 with IndexError on small grids;
    # it now returns zonal=None gracefully (Devin Review #18).
    from fastapi.testclient import TestClient

    from athletiq.api.main import app

    client = TestClient(app)
    r = client.post(
        "/api/pitch-control",
        json={
            "players": [
                {"x": 50.0, "y": 34.0, "vx": 0.0, "vy": 0.0, "team": 0},
                {"x": 55.0, "y": 34.0, "vx": 0.0, "vy": 0.0, "team": 1},
            ],
            "grid_rows": 3,
            "grid_cols": 52,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["zonal"] is None
    assert len(body["phi"]) == 3


def test_twelve_zones_cover_full_pitch() -> None:
    phi = np.full((34, 52), 0.5)
    xs, ys = _xs_ys(phi.shape)
    s = zonal_summary(phi, xs, ys)
    assert len(s.zones) == 12
    # every zone's midpoint lies inside the pitch rectangle
    for z in s.zones:
        assert 0.0 <= z.x_center <= 105.0
        assert 0.0 <= z.y_center <= 68.0
        assert z.x_range[0] <= z.x_center <= z.x_range[1]
        assert z.y_range[0] <= z.y_center <= z.y_range[1]
    # all zones on a flat surface have phi=0.5 and balance=50
    for z in s.zones:
        assert z.phi_mean == pytest.approx(0.5)
    assert s.balance_attacker_pct == pytest.approx(50.0)
    assert s.balance_defender_pct == pytest.approx(50.0)


def test_attacker_dominant_right_flank_picked_up_by_hottest_attack() -> None:
    # build a surface where the right flank of the attacking third is saturated
    phi = np.full((34, 52), 0.2)
    # right flank = last ~8 rows (y ~ 52..68), attacking third = last ~18 cols
    phi[-9:, -18:] = 0.95
    xs, ys = _xs_ys(phi.shape)
    s = zonal_summary(phi, xs, ys)
    assert s.hottest_attack.channel == "Right flank"
    assert s.hottest_attack.third == "attacking third"
    assert s.hottest_attack.phi_mean > 0.8


def test_defensive_weak_point_is_worst_phi_in_attacking_third() -> None:
    # Surface is mostly attacker-dominant, except the attacking third's left
    # flank where the defence is holding firm.
    phi = np.full((34, 52), 0.7)
    phi[:9, -18:] = 0.25  # left flank of attacking third -> defender holds
    xs, ys = _xs_ys(phi.shape)
    s = zonal_summary(phi, xs, ys)
    assert s.defensive_weak_point.third == "attacking third"
    assert s.defensive_weak_point.channel == "Left flank"
    assert s.defensive_weak_point.phi_mean < 0.3


def test_headline_mentions_all_three_zones() -> None:
    players = generate_synthetic_snapshot(seed=0)
    phi, xx, yy = pitch_control_surface(players, grid_shape=(34, 52))
    s = zonal_summary(phi, xx[0], yy[:, 0])
    assert "Attack owns" in s.headline
    assert "Defence holds" in s.headline
    assert "Territorial balance" in s.headline
    assert f"Φ={s.hottest_attack.phi_mean:.2f}" in s.headline
    assert f"Φ={s.defensive_weak_point.phi_mean:.2f}" in s.headline


def test_balance_attacker_pct_reflects_mean_phi() -> None:
    # hand-crafted surface with attacker-attacker-defender weighting
    phi = np.concatenate(
        [np.full((34, 26), 0.8), np.full((34, 26), 0.2)],
        axis=1,
    )
    xs, ys = _xs_ys(phi.shape)
    s = zonal_summary(phi, xs, ys)
    # mean 0.5 -> balance 50
    assert s.balance_attacker_pct == pytest.approx(50.0, abs=0.5)


def test_balance_gates_advice_sentence() -> None:
    # Heavily attacker-dominant: 80% of pitch at phi=0.9
    phi = np.full((34, 52), 0.9)
    xs, ys = _xs_ys(phi.shape)
    s_high = zonal_summary(phi, xs, ys)
    assert "press its dominance" in s_high.headline

    # Heavily defender-dominant: should suggest the safest build-up zone
    phi = np.full((34, 52), 0.1)
    # give one pocket of attacker safety in the attacker's defensive third,
    # right flank, so the opportunity zone is predictable
    phi[-9:, :17] = 0.6
    s_low = zonal_summary(phi, xs, ys)
    assert "safest build-up from" in s_low.headline
    assert s_low.opportunity_zone.third == "defensive third"


def test_opportunity_zone_is_best_phi_in_defensive_third() -> None:
    # Attacker already controls deep-right-flank at (x~10, y~60)
    phi = np.full((34, 52), 0.4)
    phi[-9:, :17] = 0.85  # defensive third, right flank
    xs, ys = _xs_ys(phi.shape)
    s = zonal_summary(phi, xs, ys)
    assert s.opportunity_zone.third == "defensive third"
    assert s.opportunity_zone.channel == "Right flank"
    assert s.opportunity_zone.phi_mean > 0.8


def test_endpoint_integrates_zonal_payload() -> None:
    from fastapi.testclient import TestClient

    from athletiq.api.main import app

    client = TestClient(app)
    r = client.get("/api/pitch-control/demo")
    assert r.status_code == 200
    body = r.json()
    assert "zonal" in body and body["zonal"] is not None
    z = body["zonal"]
    assert len(z["zones"]) == 12
    assert set(z["channels"]) == {
        "Left flank",
        "Left half-space",
        "Right half-space",
        "Right flank",
    }
    assert z["thirds"] == ["defensive third", "middle third", "attacking third"]
    assert "headline" in z and isinstance(z["headline"], str)
    # balance adds to 100
    assert pytest.approx(z["balance_attacker_pct"] + z["balance_defender_pct"], 0.01) == 100.0

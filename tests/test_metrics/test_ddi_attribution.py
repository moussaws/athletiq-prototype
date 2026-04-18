"""Per-player DDI attribution (ddi_attribution.simulate_match_ddi)."""

from __future__ import annotations

import pytest

from athletiq.metrics.ddi_attribution import (
    ATTACK_LINEUP,
    POSITION_MOVER_WEIGHT,
    build_attack_squad,
    simulate_match_ddi,
)


def test_build_attack_squad_has_eleven_named_players() -> None:
    squad = build_attack_squad()
    assert len(squad) == 11
    # Unique player_ids
    ids = {p.player_id for p in squad}
    assert len(ids) == 11
    # Every named attacker sits somewhere on the pitch (0 <= x <= 105)
    for p in squad:
        assert 0.0 <= p.base_x <= 105.0
        assert 0.0 <= p.base_y <= 68.0


def test_leaderboard_matches_lineup_size() -> None:
    match = simulate_match_ddi(seed=0, n_actions=40)
    assert len(match.leaderboard) == len(ATTACK_LINEUP)
    # Sorted by DDI descending.
    ddis = [p.ddi_m2 for p in match.leaderboard]
    assert ddis == sorted(ddis, reverse=True)


def test_leaderboard_nonnegative_totals() -> None:
    match = simulate_match_ddi(seed=1, n_actions=30)
    for p in match.leaderboard:
        assert p.ddi_m2 >= 0.0
        assert p.actions >= 0
        if p.actions == 0:
            assert p.avg_per_action == pytest.approx(0.0)
        else:
            assert p.avg_per_action == pytest.approx(p.ddi_m2 / p.actions, rel=1e-9)


def test_total_equals_sum_of_players() -> None:
    match = simulate_match_ddi(seed=0, n_actions=30)
    total = sum(p.ddi_m2 for p in match.leaderboard)
    assert total == pytest.approx(match.total_ddi_m2, rel=1e-9)


def test_actions_sum_matches_active_n_actions() -> None:
    """With some positions (GK) weighted at 0, a few picks become no-ops."""
    match = simulate_match_ddi(seed=0, n_actions=60)
    action_sum = sum(p.actions for p in match.leaderboard)
    # n_actions is the loop budget; zero-weight picks contribute 0 actions, so
    # the sum is <= n_actions. GK weight is 0 so we expect some drop-off.
    assert 0 <= action_sum <= 60
    # Over 60 trials, most should still land on non-zero-weight positions.
    assert action_sum >= 40


def test_forwards_rank_higher_than_defenders() -> None:
    match = simulate_match_ddi(seed=0, n_actions=80)
    by_id = {p.player_id: p for p in match.leaderboard}
    forwards = sum(by_id[a].ddi_m2 for a in ("A09", "A10", "A11"))  # WG/ST/WG
    defenders = sum(by_id[a].ddi_m2 for a in ("A02", "A03"))  # CB/CB
    # Forwards make final-third runs; CBs shifted by ~10m still don't reach
    # the high-xT zone. Forwards should dominate the DDI total by a large margin.
    assert forwards > defenders
    assert forwards > 100.0


def test_gk_never_mover() -> None:
    assert POSITION_MOVER_WEIGHT["GK"] == 0.0
    match = simulate_match_ddi(seed=3, n_actions=40)
    gk = next(p for p in match.leaderboard if p.player_id == "A01")
    assert gk.actions == 0
    assert gk.ddi_m2 == pytest.approx(0.0)


def test_deterministic_same_seed() -> None:
    a = simulate_match_ddi(seed=7, n_actions=20)
    b = simulate_match_ddi(seed=7, n_actions=20)
    assert a.total_ddi_m2 == pytest.approx(b.total_ddi_m2, rel=1e-12)
    for p_a, p_b in zip(a.leaderboard, b.leaderboard, strict=True):
        assert p_a.player_id == p_b.player_id
        assert p_a.ddi_m2 == pytest.approx(p_b.ddi_m2, rel=1e-12)


def test_different_seeds_produce_different_distributions() -> None:
    a = simulate_match_ddi(seed=0, n_actions=40)
    b = simulate_match_ddi(seed=99, n_actions=40)
    # Not identical (extremely unlikely under RNG variation).
    assert a.total_ddi_m2 != pytest.approx(b.total_ddi_m2, rel=1e-6)


def test_raises_on_invalid_arguments() -> None:
    with pytest.raises(ValueError):
        simulate_match_ddi(seed=0, n_actions=0)
    with pytest.raises(ValueError):
        simulate_match_ddi(seed=0, n_actions=5, grid_shape=(2, 2))

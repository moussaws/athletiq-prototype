"""Tests for the coach-facing insights layer."""

from __future__ import annotations

import pytest

from athletiq.data.synthetic import generate_synthetic_cohort
from athletiq.insights import (
    describe_ddi,
    describe_metric,
    describe_player_style,
    label_archetype,
    percentile_verdict,
)
from athletiq.insights.archetypes import available_archetypes


def _ref_for_position(cohort, position: str) -> dict[str, tuple[float, float]]:
    import numpy as np

    peers = [p for p in cohort if p.position == position]
    feature_names = list(peers[0].features.keys())
    arr = np.array([[p.features[f] for f in feature_names] for p in peers])
    return {
        f: (float(arr[:, i].mean()), float(arr[:, i].std())) for i, f in enumerate(feature_names)
    }


def test_archetype_palette_covers_every_position() -> None:
    for pos in ("GK", "CB", "FB", "DM", "CM", "AM", "WG", "ST"):
        names = available_archetypes(pos)
        assert len(names) >= 2, f"{pos} needs at least 2 candidate archetypes"


def test_archetype_label_prefers_passing_for_deep_lying_playmaker_centroid() -> None:
    """A CM centroid with high passes and xt and low sprints → Deep-Lying Playmaker."""
    cohort = generate_synthetic_cohort(n=80, seed=42)
    ref = _ref_for_position(cohort, "CM")
    # Engineer a centroid 2σ above on passing, 1σ above on xt, 1σ below on sprints.
    centroid = {f: mean for f, (mean, _) in ref.items()}
    centroid["passes_completed"] = ref["passes_completed"][0] + 2.0 * ref["passes_completed"][1]
    centroid["xt_carry"] = ref["xt_carry"][0] + 1.0 * ref["xt_carry"][1]
    centroid["sprint_count"] = max(0.0, ref["sprint_count"][0] - 1.0 * ref["sprint_count"][1])
    label = label_archetype("CM", centroid, ref)
    assert label.name == "Deep-Lying Playmaker"
    assert (
        "progression" in label.description.lower()
        or "short progression" in label.description.lower()
    )
    assert label.key_traits  # non-empty


def test_archetype_label_prefers_box_to_box_for_high_sprint_centroid() -> None:
    cohort = generate_synthetic_cohort(n=80, seed=42)
    ref = _ref_for_position(cohort, "CM")
    centroid = {f: mean for f, (mean, _) in ref.items()}
    centroid["sprint_count"] = ref["sprint_count"][0] + 2.0 * ref["sprint_count"][1]
    centroid["tackles"] = ref["tackles"][0] + 1.0 * ref["tackles"][1]
    centroid["xt_carry"] = ref["xt_carry"][0] + 0.5 * ref["xt_carry"][1]
    label = label_archetype("CM", centroid, ref)
    assert label.name == "Box-to-Box Raider"


def test_archetype_label_target_man_for_aerial_heavy_striker() -> None:
    cohort = generate_synthetic_cohort(n=80, seed=42)
    ref = _ref_for_position(cohort, "ST")
    centroid = {f: mean for f, (mean, _) in ref.items()}
    centroid["aerial_duels_won"] = ref["aerial_duels_won"][0] + 2.5 * ref["aerial_duels_won"][1]
    centroid["take_ons"] = max(0.0, ref["take_ons"][0] - 1.5 * ref["take_ons"][1])
    label = label_archetype("ST", centroid, ref)
    assert label.name == "Target Man"


def test_archetype_label_poacher_for_shot_heavy_striker() -> None:
    cohort = generate_synthetic_cohort(n=80, seed=42)
    ref = _ref_for_position(cohort, "ST")
    centroid = {f: mean for f, (mean, _) in ref.items()}
    centroid["shots"] = ref["shots"][0] + 2.5 * ref["shots"][1]
    centroid["passes_completed"] = max(
        0.0, ref["passes_completed"][0] - 1.5 * ref["passes_completed"][1]
    )
    centroid["xt_carry"] = max(0.0, ref["xt_carry"][0] - 1.0 * ref["xt_carry"][1])
    label = label_archetype("ST", centroid, ref)
    assert label.name == "Poacher"


def test_archetype_label_unknown_position_falls_back() -> None:
    label = label_archetype("XX", {}, {})
    assert label.name.startswith("XX")
    assert label.key_traits == []


def test_percentile_verdict_bands() -> None:
    pool = [float(i) for i in range(100)]
    p_elite, band_elite = percentile_verdict(98.0, pool)
    assert p_elite >= 95
    assert band_elite == "elite"
    p_avg, band_avg = percentile_verdict(50.0, pool)
    assert 40 <= p_avg <= 60
    assert band_avg == "average"
    p_weak, band_weak = percentile_verdict(1.0, pool)
    assert p_weak < 20
    assert band_weak == "weak"


def test_describe_metric_with_pool_mentions_peer_comparison() -> None:
    pool = [float(i) for i in range(100)]
    verdict = describe_metric("xt_carry", 90.0, pool=pool)
    assert "top" in verdict.headline.lower()
    assert verdict.percentile is not None
    assert verdict.band == "strong" or verdict.band == "elite"


def test_describe_metric_without_pool_gracefully_drops_percentile() -> None:
    verdict = describe_metric("xt_carry", 0.3)
    assert verdict.percentile is None
    assert "0.30" in verdict.headline


def test_describe_ddi_low_and_high_tiers() -> None:
    high = describe_ddi(800.0, 50)
    low = describe_ddi(20.0, 30)
    zero = describe_ddi(0.0, 0)
    assert "elite" in high.lower()
    assert "low impact" in low.lower()
    assert "no on-ball actions" in zero.lower()


def test_describe_player_style_picks_highlights_above_noise_floor() -> None:
    cohort = generate_synthetic_cohort(n=80, seed=7)
    ref = _ref_for_position(cohort, "WG")
    # Winger with notable shots + take_ons (inside-forward style)
    peer = next(p for p in cohort if p.position == "WG")
    # Synthesise a spike profile rather than relying on sampling luck.
    spike_features = dict(peer.features)
    spike_features["shots"] = ref["shots"][0] + 2.0 * ref["shots"][1]
    spike_features["take_ons"] = ref["take_ons"][0] + 2.0 * ref["take_ons"][1]
    style = describe_player_style("WG", spike_features, ref)
    assert "WG" in style
    # Should mention at least one of the spiked-trait phrasings.
    assert any(
        phrase in style.lower() for phrase in ("goal threat", "1-v-1 dribbling", "dribbling")
    )


def test_describe_player_style_balanced_profile_has_no_standout() -> None:
    cohort = generate_synthetic_cohort(n=80, seed=7)
    ref = _ref_for_position(cohort, "CB")
    centroid = {f: mean for f, (mean, _) in ref.items()}
    style = describe_player_style("CB", centroid, ref)
    assert "balanced" in style.lower()


@pytest.mark.parametrize("pos", ["GK", "CB", "FB", "DM", "CM", "AM", "WG", "ST"])
def test_label_archetype_returns_palette_member(pos: str) -> None:
    """Whatever centroid we feed, the label should be one of the palette options."""
    cohort = generate_synthetic_cohort(n=80, seed=1)
    ref = _ref_for_position(cohort, pos)
    peer = next(p for p in cohort if p.position == pos)
    label = label_archetype(pos, peer.features, ref)
    assert label.name in available_archetypes(pos)

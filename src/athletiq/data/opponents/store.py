"""Domain types and Protocol for opponent profile storage.

A store is *feed-agnostic*: callers never see vendor-specific schemas. v1
ships :class:`StatsBombOpenStore` (CC BY-NC-SA 4.0, internal/demo only);
v2 will add a paid-feed implementation behind the same Protocol.

Profiles are intentionally small (5-50 KB JSON each) so we can serialise
them to disk and ship them in the repo as fixtures for the spike and as
seed data for downstream environments.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class HistogramSamples:
    """Compact 1-D distribution as paired bin-edges + counts.

    ``bin_edges`` has length ``len(counts) + 1``; bin ``i`` covers
    ``[bin_edges[i], bin_edges[i+1])``. Sampling is one ``numpy.choice``
    call against ``counts`` followed by uniform jitter inside the chosen
    bin — implementations may keep the underlying samples too if they
    need higher fidelity than histogram quantiles.
    """

    bin_edges: list[float]
    counts: list[int]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> HistogramSamples:
        return cls(bin_edges=list(d["bin_edges"]), counts=list(d["counts"]))


@dataclass(frozen=True, slots=True)
class OpponentProfile:
    """A team's typical posture and on-ball footprint, aggregated from
    one or more matches in a single competition+season.

    All spatial fields use the canonical 105 × 68 m pitch with the
    profiled team attacking toward +x. Implementations are responsible
    for mirroring per-match coordinates so this convention always holds.
    """

    opponent_id: str
    """Slug, stable across runs. e.g. ``"bayer-leverkusen-2023-24"``."""

    display_name: str
    """Human-readable label for the UI dropdown."""

    source_attribution: str
    """License + vendor string surfaced verbatim in the UI."""

    competition: str
    """Free-text competition name. e.g. ``"Bundesliga"``."""

    season: str
    """Season label as published by the source. e.g. ``"2023/2024"``."""

    matches_observed: int
    """Number of matches the profile aggregates."""

    formation_mix: list[tuple[str, float]]
    """List of ``(formation, weight)`` pairs. Weights sum to 1.0.
    Driven by the team's *starting* formation per match."""

    def_line_height_distribution: HistogramSamples
    """Distribution of per-match mean defensive-line height in metres,
    from the team's own goal-line. Higher = pressed higher."""

    pressing_intensity_per_zone: list[list[float]]
    """4 horizontal channels × 3 vertical thirds. Values are
    counts per 90-min normalised so the grid sums to 1.0."""

    positional_heatmap: list[list[float]]
    """34 × 52 grid (row-major). On-ball event density when the team is
    in possession. Normalised so the grid sums to 1.0."""

    transition_speed_proxy: float = 0.0
    """Mean ball-progression speed (m/s) in the first 5 s after a
    Recovery event. ``0.0`` when not yet computed (v1 placeholder)."""

    notes: list[str] = field(default_factory=list)
    """Anything the ingester wants to surface to a human reader."""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["def_line_height_distribution"] = self.def_line_height_distribution.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> OpponentProfile:
        kwargs = dict(d)
        kwargs["def_line_height_distribution"] = HistogramSamples.from_dict(
            d["def_line_height_distribution"]
        )
        # JSON deserialises tuples as lists; coerce formation_mix back.
        kwargs["formation_mix"] = [tuple(p) for p in d["formation_mix"]]
        return cls(**kwargs)


class OpponentEventStore(Protocol):
    """Feed-agnostic store. v2 paid-feed swap implements the same surface."""

    def list_opponents(self) -> list[tuple[str, str]]:
        """Return ``[(opponent_id, display_name), ...]`` for every
        registered opponent."""

    def get_profile(self, opponent_id: str) -> OpponentProfile:
        """Fetch one profile by ID. Raises ``KeyError`` if unknown."""

    def attribution_text(self) -> str:
        """The license/vendor line to surface in the UI when this store
        backs the active opponent."""

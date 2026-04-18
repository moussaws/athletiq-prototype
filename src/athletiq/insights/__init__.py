"""Coach-facing insight translation layer.

Turns raw metric values and cluster centroids into plain football language
(archetype labels from the paper, percentile verdicts, one-sentence styles).
The mathematical models stay untouched; this layer sits on top.
"""

from athletiq.insights.archetypes import ArchetypeLabel, label_archetype
from athletiq.insights.match import (
    MatchNarrative,
    TeamSummary,
    TopPerformer,
    build_match_narrative,
)
from athletiq.insights.translator import (
    MetricVerdict,
    describe_ddi,
    describe_metric,
    describe_player_style,
    percentile_verdict,
)

__all__ = [
    "ArchetypeLabel",
    "MatchNarrative",
    "MetricVerdict",
    "TeamSummary",
    "TopPerformer",
    "build_match_narrative",
    "describe_ddi",
    "describe_metric",
    "describe_player_style",
    "label_archetype",
    "percentile_verdict",
]

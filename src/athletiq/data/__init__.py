"""Data loaders — synthetic generators + StatsBomb Open Data adapter."""

from athletiq.data.statsbomb import (
    load_statsbomb_match_player_vectors,
    statsbomb_available,
)
from athletiq.data.synthetic import (
    generate_synthetic_cohort,
    generate_synthetic_possession,
    generate_synthetic_snapshot,
)

__all__ = [
    "generate_synthetic_cohort",
    "generate_synthetic_possession",
    "generate_synthetic_snapshot",
    "load_statsbomb_match_player_vectors",
    "statsbomb_available",
]

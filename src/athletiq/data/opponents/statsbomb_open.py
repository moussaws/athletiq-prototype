"""StatsBomb Open Data implementation of :class:`OpponentEventStore`.

License: CC BY-NC-SA 4.0 — see :mod:`athletiq.data.opponents.license_gate`.
This store is fenced away from production environments by the gate; any
read goes through ``assert_license_tier_allows(store_tier="open")`` first.

Aggregation strategy
--------------------

For each registered opponent, we walk every match the team played in the
configured competition+season and aggregate four spatial signals from
the open events stream:

1. **formation_mix** — starting formation (from the first ``Starting XI``
   tactical event per match), weighted by frequency across matches.
2. **def_line_height_distribution** — per-match mean ``x`` of defensive
   actions (Pressure, Tackle, Interception, Block, Clearance) when the
   team is OUT of possession, mirrored so ``x`` is always measured from
   the team's own goal line. Histogram of those per-match means.
3. **pressing_intensity_per_zone** — count of ``Pressure`` events per
   90-minute equivalent in each cell of a 4×3 grid (channels × thirds),
   normalised so the grid sums to 1.0.
4. **positional_heatmap** — on-ball event density in a 34×52 grid when
   the team is in possession, normalised so the grid sums to 1.0.

``transition_speed_proxy`` is left at the default ``0.0`` for v1 — it
needs sequence-level analysis (events within 5 s of a Recovery) that's
worth a follow-up ticket, not the spike.

Caching
-------

Profile JSON files are written to
``src/athletiq/data/opponents/profiles/<opponent_id>.json`` on first
ingest and read back from disk on subsequent calls. They're checked into
the repo so every clone gets the same fixtures without needing the
network.
"""

from __future__ import annotations

import json
import logging
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from athletiq.data.opponents.license_gate import assert_license_tier_allows
from athletiq.data.opponents.store import (
    HistogramSamples,
    OpponentProfile,
)

try:
    from statsbombpy import sb  # type: ignore

    _STATSBOMB_AVAILABLE = True
except ImportError:  # pragma: no cover
    sb = None  # type: ignore[assignment]
    _STATSBOMB_AVAILABLE = False


logger = logging.getLogger(__name__)


# StatsBomb's pitch is 120 × 80 (in their event coords). Athletiq canonical
# is 105 × 68. Constant scale factors keep the conversion fast and obvious.
_SB_PITCH_LENGTH = 120.0
_SB_PITCH_WIDTH = 80.0
_PITCH_LENGTH_M = 105.0
_PITCH_WIDTH_M = 68.0

_HEATMAP_ROWS = 34
_HEATMAP_COLS = 52
_PRESSING_CHANNELS = 4  # left wing / left half-space / right half-space / right wing
_PRESSING_THIRDS = 3  # defensive / middle / attacking


@dataclass(frozen=True, slots=True)
class _OpponentSpec:
    """Static registration for one opponent the store will surface."""

    opponent_id: str
    display_name: str
    team_name: str  # exact StatsBomb team string
    competition: str
    season: str
    competition_id: int
    season_id: int


# v1 registry. Adding an opponent is a single tuple here; the store
# auto-discovers it via ``list_opponents``.
_REGISTRY: tuple[_OpponentSpec, ...] = (
    _OpponentSpec(
        opponent_id="bayer-leverkusen-2023-24",
        display_name="Bayer Leverkusen — Bundesliga 2023/24",
        team_name="Bayer Leverkusen",
        competition="1. Bundesliga",
        season="2023/2024",
        competition_id=9,
        season_id=281,
    ),
)


_PROFILES_DIR = Path(__file__).resolve().parent / "profiles"


_ATTRIBUTION = "StatsBomb Open Data — CC BY-NC-SA 4.0. https://github.com/statsbomb/open-data"


class StatsBombOpenStore:
    """v1 OpponentEventStore implementation backed by StatsBomb Open Data.

    Parameters
    ----------
    profiles_dir : Path | None
        Override the on-disk profiles cache. Defaults to the
        repo-committed ``src/athletiq/data/opponents/profiles/``.
    """

    store_tier: str = "open"

    def __init__(self, profiles_dir: Path | None = None) -> None:
        # Fail-closed gate runs at construction so we cannot accidentally
        # build an open-data store in a production environment.
        assert_license_tier_allows(store_tier=self.store_tier)
        self._profiles_dir = profiles_dir or _PROFILES_DIR
        self._profiles_dir.mkdir(parents=True, exist_ok=True)

    # ----- Protocol surface -------------------------------------------------

    def list_opponents(self) -> list[tuple[str, str]]:
        return [(s.opponent_id, s.display_name) for s in _REGISTRY]

    def get_profile(self, opponent_id: str) -> OpponentProfile:
        spec = self._find_spec(opponent_id)
        cached = self._read_cache(opponent_id)
        if cached is not None:
            return cached
        profile = self._build_profile(spec)
        self._write_cache(profile)
        return profile

    def attribution_text(self) -> str:
        return _ATTRIBUTION

    # ----- Internal --------------------------------------------------------

    def _find_spec(self, opponent_id: str) -> _OpponentSpec:
        for s in _REGISTRY:
            if s.opponent_id == opponent_id:
                return s
        raise KeyError(opponent_id)

    def _cache_path(self, opponent_id: str) -> Path:
        return self._profiles_dir / f"{opponent_id}.json"

    def _read_cache(self, opponent_id: str) -> OpponentProfile | None:
        path = self._cache_path(opponent_id)
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as f:
                return OpponentProfile.from_dict(json.load(f))
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("Cached profile %s is malformed (%s); re-ingesting.", path, e)
            return None

    def _write_cache(self, profile: OpponentProfile) -> None:
        path = self._cache_path(profile.opponent_id)
        with path.open("w", encoding="utf-8") as f:
            json.dump(profile.to_dict(), f, indent=2, sort_keys=True)

    def _build_profile(self, spec: _OpponentSpec) -> OpponentProfile:
        if not _STATSBOMB_AVAILABLE:
            raise RuntimeError(
                "statsbombpy is not installed; cannot ingest opponent profiles. "
                "Run `pip install -e '.[statsbomb]'`."
            )

        with warnings.catch_warnings():
            # statsbombpy emits a NoAuthWarning on every call when running
            # against open data. Quiet for the duration of the ingest.
            warnings.simplefilter("ignore")

            matches_df = sb.matches(
                competition_id=spec.competition_id,
                season_id=spec.season_id,
            )

            team_matches = matches_df[
                (matches_df["home_team"] == spec.team_name)
                | (matches_df["away_team"] == spec.team_name)
            ]
            match_ids = [int(mid) for mid in team_matches["match_id"].tolist()]

            formation_counts: dict[str, int] = {}
            line_heights_m: list[float] = []
            pressing_grid = np.zeros((_PRESSING_CHANNELS, _PRESSING_THIRDS), dtype=np.float64)
            heatmap = np.zeros((_HEATMAP_ROWS, _HEATMAP_COLS), dtype=np.float64)

            for match_id in match_ids:
                events = sb.events(match_id=match_id)
                self._aggregate_one_match(
                    spec.team_name,
                    events,
                    formation_counts,
                    line_heights_m,
                    pressing_grid,
                    heatmap,
                )

        formation_mix = _normalise_formation_counts(formation_counts)
        line_hist = _build_histogram(line_heights_m, n_bins=12, lo=0.0, hi=_PITCH_LENGTH_M)
        pressing_norm = _normalise_grid(pressing_grid)
        heatmap_norm = _normalise_grid(heatmap)

        notes = [
            f"Built from {len(match_ids)} {spec.team_name} matches in "
            f"{spec.competition} {spec.season}.",
            "transition_speed_proxy left at 0.0 (v1 — needs sequence analysis).",
        ]

        return OpponentProfile(
            opponent_id=spec.opponent_id,
            display_name=spec.display_name,
            source_attribution=_ATTRIBUTION,
            competition=spec.competition,
            season=spec.season,
            matches_observed=len(match_ids),
            formation_mix=formation_mix,
            def_line_height_distribution=line_hist,
            pressing_intensity_per_zone=pressing_norm.tolist(),
            positional_heatmap=heatmap_norm.tolist(),
            transition_speed_proxy=0.0,
            notes=notes,
        )

    @staticmethod
    def _aggregate_one_match(
        team_name: str,
        events,  # pandas DataFrame
        formation_counts: dict[str, int],
        line_heights_m: list[float],
        pressing_grid: np.ndarray,
        heatmap: np.ndarray,
    ) -> None:
        # Defensive: ensure required columns exist
        for col in (
            "type",
            "team",
            "location",
            "tactics",
            "play_pattern",
            "possession_team",
        ):
            if col not in events.columns:
                events[col] = None

        # Starting formation: first Starting XI event for the team. The
        # ``tactics`` cell is a dict like ``{"formation": 3421, "lineup": [...]}``.
        starting_xi = events[(events["type"] == "Starting XI") & (events["team"] == team_name)]
        if len(starting_xi) > 0:
            tactics = starting_xi.iloc[0].get("tactics")
            formation = tactics.get("formation") if isinstance(tactics, dict) else None
            if formation is not None:
                key = _format_formation(formation)
                formation_counts[key] = formation_counts.get(key, 0) + 1

        # Defensive line height: mean x of defensive actions when not in possession,
        # converted to "metres from own goal line" in canonical 105m frame.
        defensive_types = {"Pressure", "Duel", "Interception", "Block", "Clearance"}
        team_defensive = events[
            (events["team"] == team_name)
            & (events["type"].isin(defensive_types))
            & (events["possession_team"] != team_name)
            & (events["location"].notna())
        ]
        if len(team_defensive) > 0:
            xs_sb = [_safe_x(loc) for loc in team_defensive["location"]]
            xs_sb = [x for x in xs_sb if x is not None]
            if xs_sb:
                # In StatsBomb coords the team always attacks left → right
                # (x increases toward opponent's goal). So mean x of THEIR
                # defensive events when defending = "how far from own goal
                # line they're winning the ball back". Convert to metres.
                mean_x_sb = float(np.mean(xs_sb))
                mean_x_m = mean_x_sb * (_PITCH_LENGTH_M / _SB_PITCH_LENGTH)
                line_heights_m.append(mean_x_m)

        # Pressing intensity: count Pressure events per zone (4 channels × 3 thirds)
        team_pressures = events[
            (events["team"] == team_name)
            & (events["type"] == "Pressure")
            & (events["location"].notna())
        ]
        for loc in team_pressures["location"]:
            x_sb = _safe_x(loc)
            y_sb = _safe_y(loc)
            if x_sb is None or y_sb is None:
                continue
            channel = int(
                np.clip(y_sb / _SB_PITCH_WIDTH * _PRESSING_CHANNELS, 0, _PRESSING_CHANNELS - 1)
            )
            third = int(
                np.clip(x_sb / _SB_PITCH_LENGTH * _PRESSING_THIRDS, 0, _PRESSING_THIRDS - 1)
            )
            pressing_grid[channel, third] += 1

        # Positional heatmap: on-ball events when the team is in possession.
        # Use Pass + Carry + Dribble + Shot as the "on-ball" set.
        on_ball_types = {"Pass", "Carry", "Dribble", "Shot"}
        in_poss = events[
            (events["team"] == team_name)
            & (events["type"].isin(on_ball_types))
            & (events["possession_team"] == team_name)
            & (events["location"].notna())
        ]
        for loc in in_poss["location"]:
            x_sb = _safe_x(loc)
            y_sb = _safe_y(loc)
            if x_sb is None or y_sb is None:
                continue
            col = int(np.clip(x_sb / _SB_PITCH_LENGTH * _HEATMAP_COLS, 0, _HEATMAP_COLS - 1))
            row = int(np.clip(y_sb / _SB_PITCH_WIDTH * _HEATMAP_ROWS, 0, _HEATMAP_ROWS - 1))
            heatmap[row, col] += 1


# ─── small helpers ─────────────────────────────────────────────────────────


def _safe_x(loc) -> float | None:
    if loc is None:
        return None
    try:
        return float(loc[0])
    except (TypeError, ValueError, IndexError):
        return None


def _safe_y(loc) -> float | None:
    if loc is None:
        return None
    try:
        return float(loc[1])
    except (TypeError, ValueError, IndexError):
        return None


def _format_formation(raw) -> str:
    """StatsBomb encodes formation as e.g. ``433`` or ``"433"``. Convert
    to the canonical ``"4-3-3"`` style the app uses elsewhere."""
    s = str(int(raw)) if isinstance(raw, (int, float)) else str(raw).strip()
    return "-".join(s)


def _normalise_formation_counts(counts: dict[str, int]) -> list[tuple[str, float]]:
    if not counts:
        return []
    total = sum(counts.values())
    items = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    return [(formation, n / total) for formation, n in items]


def _build_histogram(
    samples: list[float], *, n_bins: int, lo: float, hi: float
) -> HistogramSamples:
    if not samples:
        return HistogramSamples(bin_edges=[lo, hi], counts=[0])
    counts, edges = np.histogram(samples, bins=n_bins, range=(lo, hi))
    return HistogramSamples(
        bin_edges=[float(e) for e in edges],
        counts=[int(c) for c in counts],
    )


def _normalise_grid(grid: np.ndarray) -> np.ndarray:
    total = float(grid.sum())
    if total <= 0:
        return grid
    return grid / total

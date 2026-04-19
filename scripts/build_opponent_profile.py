"""Build (or rebuild) an opponent profile from StatsBomb Open Data.

Usage:

    ATHLETIQ_LICENSE_TIER=open ATHLETIQ_ENV=dev \\
      python scripts/build_opponent_profile.py bayer-leverkusen-2023-24

Prints a summary of the produced profile (formation mix, line-height
histogram, pressing-grid totals, heatmap quartiles) so a human can eyeball
the shape against what the tech design assumes.

The JSON is written to ``src/athletiq/data/opponents/profiles/<id>.json``
and committed to the repo.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

from athletiq.data.opponents.statsbomb_open import StatsBombOpenStore


def _summarise(profile_id: str) -> int:
    store = StatsBombOpenStore()
    available = dict(store.list_opponents())
    if profile_id not in available:
        print(f"Unknown opponent_id: {profile_id!r}", file=sys.stderr)
        print(f"Available: {sorted(available)}", file=sys.stderr)
        return 2

    print(f"Building profile for {profile_id} — {available[profile_id]} ...")
    print(f"  Source: {store.attribution_text()}")

    # Force a re-ingest by removing any cached JSON first.
    cache_path = Path(__file__).resolve().parent.parent / (
        f"src/athletiq/data/opponents/profiles/{profile_id}.json"
    )
    if cache_path.exists():
        print(f"  Removing cached {cache_path.name} to force fresh ingest.")
        cache_path.unlink()

    profile = store.get_profile(profile_id)

    print()
    print(f"  Matches observed:        {profile.matches_observed}")
    print(f"  Competition / season:    {profile.competition} {profile.season}")
    print()
    print("  Formation mix (starting XI):")
    for formation, weight in profile.formation_mix:
        bar = "█" * int(round(weight * 40))
        print(f"    {formation:>8s}  {weight:>5.1%}  {bar}")
    print()
    print("  Defensive-line-height histogram (metres from own goal line):")
    edges = profile.def_line_height_distribution.bin_edges
    counts = profile.def_line_height_distribution.counts
    if max(counts) > 0:
        max_count = max(counts)
        for i, c in enumerate(counts):
            lo, hi = edges[i], edges[i + 1]
            bar = "█" * int(round(c / max_count * 30))
            print(f"    {lo:>5.1f} - {hi:>5.1f} m   ({c:>3d} matches)  {bar}")
    else:
        print("    (empty)")
    print()
    pressing = np.asarray(profile.pressing_intensity_per_zone)
    print(f"  Pressing grid (4 channels × 3 thirds, sum={pressing.sum():.4f}):")
    for ch in range(pressing.shape[0]):
        row = "  ".join(f"{v:.3f}" for v in pressing[ch])
        print(f"    ch{ch}:  {row}")
    print("    (rows: top→bottom = +y to -y; cols: defensive → middle → attacking)")
    print()
    heatmap = np.asarray(profile.positional_heatmap)
    print(f"  Positional heatmap shape: {heatmap.shape} (sum={heatmap.sum():.4f})")
    print(f"    Hottest cell value: {heatmap.max():.4f}")
    print(f"    P95 cell value:     {np.percentile(heatmap, 95):.4f}")
    print(f"    Median cell value:  {np.percentile(heatmap, 50):.4f}")
    print()
    print("  Notes:")
    for note in profile.notes:
        print(f"    - {note}")
    print()
    print(f"Wrote {cache_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("opponent_id", help="ID from StatsBombOpenStore.list_opponents()")
    args = parser.parse_args()
    return _summarise(args.opponent_id)


if __name__ == "__main__":
    raise SystemExit(main())

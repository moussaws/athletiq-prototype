"""AthletIQ CLI — seed data, run the end-to-end demo, serve the API."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

from athletiq import __version__
from athletiq.api.state import bootstrap, get_store, reset_store
from athletiq.data.synthetic import generate_synthetic_possession, generate_synthetic_snapshot
from athletiq.metrics import (
    ddi,
    mean_collective_pressure,
    pitch_control_surface,
    progressive_carry_xt,
)
from athletiq.metrics.retention import PossessionSequence
from athletiq.metrics.retention import pabr as pabr_fn
from athletiq.scouting.ahp import ahp_weights, consistency_ratio
from athletiq.scouting.bip import optimize_squad
from athletiq.scouting.waspas import normalize_benefit, waspas_scores


def _apply_source(args: argparse.Namespace) -> None:
    if getattr(args, "synthetic", False):
        os.environ["ATHLETIQ_COHORT_SOURCE"] = "synthetic"
    else:
        os.environ.pop("ATHLETIQ_COHORT_SOURCE", None)
    reset_store()


def _cmd_seed(args: argparse.Namespace) -> int:
    _apply_source(args)
    store = bootstrap()
    print(
        f"[seed] {len(store.players)} players loaded ({store.provenance.get('source')}); "
        f"PCA kept {store.pca.explained_variance:.1%} of variance in "
        f"{store.pca.X_reduced.shape[1]} components."
    )
    return 0


def _cmd_demo(args: argparse.Namespace) -> int:
    print(f"AthletIQ prototype v{__version__} — end-to-end demo")
    print("=" * 64)

    # Pillar A — synthetic possession + PABR
    seqs = []
    for i in range(30):
        pl = 0.2 + (i % 5) * 0.2
        seq = generate_synthetic_possession(pressure_level=pl, retained=(i % 3 != 0), seed=i)
        mean_p = mean_collective_pressure(seq.defenders_pos, seq.carrier_pos)
        seqs.append(PossessionSequence(mean_pressure=mean_p, retained=seq.retained))
    pabr_val = pabr_fn(seqs)
    carry_val = progressive_carry_xt((30, 34), (78, 30), mean_pressure=3.5)
    print(f"[metrics] PABR (synthetic)           = {pabr_val:.3f}")
    print(f"[metrics] Progressive Carry xT demo  = {carry_val:.3f}")

    # Pitch Control + DDI
    before = generate_synthetic_snapshot(seed=args.seed)
    phi_b, xx, yy = pitch_control_surface(before, grid_shape=(34, 52))
    phi_a = np.clip(phi_b + 0.08, 0, 1)  # fake distortion for the demo
    print(f"[metrics] Pitch Control mean         = {phi_b.mean():.3f}")
    print(f"[metrics] DDI (synthetic upgrade)    = {ddi(phi_b, phi_a, xx, yy):.1f} m^2")

    # Pillar B — cohort + AHP + WASPAS + BIP
    _apply_source(args)
    store = bootstrap()
    print()
    print(
        f"[scouting] cohort={len(store.players)} players, PCA dims={store.pca.X_reduced.shape[1]}"
    )

    criteria = ["pabr", "xt_carry", "ddi", "passes_completed", "interceptions"]
    A = np.array(
        [
            [1, 2, 3, 4, 5],
            [1 / 2, 1, 2, 3, 4],
            [1 / 3, 1 / 2, 1, 2, 3],
            [1 / 4, 1 / 3, 1 / 2, 1, 2],
            [1 / 5, 1 / 4, 1 / 3, 1 / 2, 1],
        ],
        dtype=np.float64,
    )
    w = ahp_weights(A)
    cr = consistency_ratio(A)
    print(f"[AHP]    CR = {cr:.3f} ({'consistent' if cr < 0.10 else 'INCONSISTENT'})")
    for c, wi in zip(criteria, w.tolist(), strict=True):
        print(f"          w[{c:<20}] = {wi:.3f}")

    # Formation and price cap
    formation = {"GK": 1, "CB": 2, "FB": 2, "DM": 1, "CM": 2, "AM": 1, "WG": 1, "ST": 1}
    positions = list(formation.keys())

    feat_names = list(store.players[0].features.keys())
    feat_idx = [feat_names.index(c) for c in criteria]
    raw = np.array(
        [[p.features.get(fn, 0.0) for fn in feat_names] for p in store.players],
        dtype=np.float64,
    )

    N = len(store.players)
    P = len(positions)
    Y = np.zeros((N, P))
    for pi, pos in enumerate(positions):
        mask = np.array([p.position == pos for p in store.players])
        if not mask.any():
            continue
        Y_pos = raw[mask][:, feat_idx]
        Y_norm = normalize_benefit(Y_pos)
        Y[mask, pi] = waspas_scores(Y_norm, w)

    result = optimize_squad(
        Q=Y,
        player_ids=[p.player_id for p in store.players],
        positions=positions,
        formation=formation,
        foreign_flags=[p.is_foreign for p in store.players],
        market_values=[p.market_value_m for p in store.players],
        budget=500.0,
        foreign_max=5,
    )
    print()
    print(
        f"[BIP] optimal lineup Q_total = {result.total_score:.3f}; "
        f"budget used = {result.budget_used:.1f}M; "
        f"foreigners = {result.foreign_count}"
    )
    print(f"[BIP] squad gap = {result.squad_gap_position} (delta Q = {result.squad_gap_delta:.3f})")
    return 0


def _cmd_version(_args: argparse.Namespace) -> int:
    print(__version__)
    return 0


def _cmd_export(_args: argparse.Namespace) -> int:
    """Dump a JSON snapshot of the current cohort — useful for Next.js static props."""
    store = get_store()
    payload = {
        "version": __version__,
        "n": len(store.players),
        "players": [
            {
                "player_id": p.player_id,
                "name": p.name,
                "position": p.position,
                "nationality": p.nationality,
                "age": p.age,
                "market_value_m": p.market_value_m,
                "is_foreign": p.is_foreign,
                "features": p.features,
            }
            for p in store.players
        ],
    }
    out = Path(_args.out)
    out.write_text(json.dumps(payload, indent=2))
    print(f"[export] wrote {out} ({out.stat().st_size / 1024:.1f} KiB)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="athletiq", description="AthletIQ prototype CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_seed = sub.add_parser("seed", help="load the in-memory player cohort")
    p_seed.add_argument("--synthetic", action="store_true", help="force the synthetic cohort")
    p_seed.set_defaults(func=_cmd_seed)

    p_demo = sub.add_parser("demo", help="run full end-to-end demo in the terminal")
    p_demo.add_argument("--synthetic", action="store_true", help="force the synthetic cohort")
    p_demo.add_argument("--seed", type=int, default=42, help="random seed for possession synth")
    p_demo.set_defaults(func=_cmd_demo)

    p_ver = sub.add_parser("version", help="print version")
    p_ver.set_defaults(func=_cmd_version)

    p_exp = sub.add_parser("export", help="export the cohort as JSON")
    p_exp.add_argument("--out", default="data/cohort.json")
    p_exp.set_defaults(func=_cmd_export)

    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    sys.exit(main())

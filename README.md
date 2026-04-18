# AthletIQ — Functional Prototype

End-to-end reference implementation of the deeptech football analytics system
described in the AthletIQ research paper:

1. **Pillar A — Context-aware metrics.** Pressure field (Eq. 1–4),
   Press-Adjusted Absolute Ball Retention / PABR (Eq. 5), pressure-weighted
   progressive carry xT (Eq. 6), Pitch Control surface (Eq. 7), Defensive
   Distortion Index / DDI (Eq. 8).
2. **Pillar B — AI scouting.** Per-position PCA → silhouette-optimal K-Means
   (Eq. 10) → hybrid KNN retrieval (Eq. 11) → AHP with consistency check
   (Eq. 12) → WASPAS fitness (Eq. 13) → Binary Integer Programming roster
   optimization + Squad Gap (Eq. 14–18).
3. **Pillar C — Single-camera CV.** YOLOv10 detection → ByteTrack tracking
   → classical Huber-robust homography from semantic pitch keypoints
   (Eq. 12 voter), producing pitch-metric trajectories consumable by
   Pillar A.

> The prototype is **not production-ready**. v2 seams explicitly deferred:
> Pixel-NeRF refinement, triplet-loss Re-ID training, VAEP, SoccerNet
> fine-tunes, TensorRT / ONNX edge optimization, full Arabic RTL i18n.

## Architecture

```
athletiq-prototype/
├── src/athletiq/
│   ├── metrics/        # Pillar A — pressure, PABR, xT, pitch-control, DDI
│   ├── scouting/       # Pillar B — PCA, K-Means, KNN, AHP, WASPAS, BIP
│   ├── cv/             # Pillar C — YOLOv10 + ByteTrack + homography
│   ├── data/           # Synthetic generator + StatsBomb adapter
│   ├── api/            # FastAPI app exposing all three pillars
│   └── cli.py          # `athletiq demo | seed | export | version`
├── web/                # Next.js 14 dashboard (App Router + Tailwind)
├── tests/              # pytest — every formula unit-tested
├── notebooks/          # Jupyter walkthroughs
├── docker-compose.yml  # postgres + api + web
├── Makefile            # make demo | test | api | web | docker-up | seed
└── pyproject.toml      # hatchling build, uv-friendly
```

## Quickstart (local, no Docker)

Requires Python **3.11+** and Node **20+** with `pnpm`.

```bash
# Install backend + run tests
make install-dev
make lint && make test

# Run the end-to-end CLI demo
make demo

# Start the FastAPI backend on :8000 (OpenAPI @ /docs)
make api

# In a second terminal, start the Next.js dashboard on :3000
cd web && pnpm install && pnpm dev
```

## Quickstart (Docker Compose)

```bash
make docker-up   # Postgres, API (:8000), Web (:3000)
```

Then open:

* API docs: http://localhost:8000/docs
* Dashboard: http://localhost:3000

## Pillar A — context-aware metrics

All equations live in `src/athletiq/metrics/`. Each has a unit test that
validates against a hand-computed value.

```python
from athletiq.metrics import (
    raw_individual_pressure, collective_pressure,
    mean_collective_pressure, pabr, progressive_carry_xt,
    pitch_control_surface, ddi,
)
from athletiq.metrics.retention import PossessionSequence

# Eq. 1 raw pressure
raw_individual_pressure([[1, 0]], [0, 0], radius=5.0)  # -> array([16.])

# Eq. 5 PABR
pabr([
    PossessionSequence(mean_pressure=0.1, retained=True),
    PossessionSequence(mean_pressure=3.5, retained=True),
    PossessionSequence(mean_pressure=0.2, retained=False),
])  # -> weighted by exp(mean_pressure)

# Eq. 6 progressive carry xT
progressive_carry_xt(start_xy=(20, 34), end_xy=(80, 30), mean_pressure=3.5)
```

## Pillar B — AI scouting

```python
from athletiq.data.synthetic import generate_synthetic_cohort
from athletiq.scouting import (
    build_feature_matrix, fit_pca, fit_kmeans_silhouette,
    knn_similar_players, ahp_weights, consistency_ratio, waspas_scores,
    optimize_squad,
)

players = generate_synthetic_cohort(n=240, seed=42)
meta, X = build_feature_matrix(players)
pca = fit_pca(X, variance_target=0.90)
clust = fit_kmeans_silhouette(pca.X_reduced)   # silhouette-optimal k
```

The `POST /api/squad` endpoint combines AHP weights + WASPAS + BIP to produce
the optimal starting XI subject to formation, budget, and foreign-quota
constraints — and identifies the *Squad Gap* (position with highest marginal
upgrade value).

## Pillar C — Computer Vision

The CV stack (`torch`, `ultralytics`, `supervision`) is an optional extra:

```bash
pip install -e ".[dev,cv]"
```

Upload an MP4 to `POST /api/cv/analyze`; the pipeline runs YOLOv10 detection,
ByteTrack tracking, and — if you pass pitch keypoint correspondences —
Huber-robust classical homography refinement to emit pitch-metric
trajectories.

```bash
curl -X POST http://localhost:8000/api/cv/analyze \
  -F "video=@clip.mp4" \
  -F 'keypoints_json={"image_pts":[[...]], "pitch_pts":[[...]]}' \
  -F "max_frames=60"
```

## `make demo`

Runs a full end-to-end slice in the terminal: generates 240 synthetic players,
computes PABR / carry xT / Pitch Control / DDI, runs AHP + WASPAS + BIP, and
prints the optimal lineup + Squad Gap.

```
$ make demo
AthletIQ prototype v0.1.0 — end-to-end demo
[metrics] PABR (synthetic)           = 0.743
[metrics] Progressive Carry xT demo  = 0.172
[metrics] Pitch Control mean         = 0.468
[metrics] DDI (synthetic upgrade)    = 782.4 m^2
[scouting] cohort=240 players, PCA dims=9
[AHP]    CR = 0.041 (consistent)
[BIP] optimal lineup Q_total = 8.912; budget used = 142.7M; foreigners = 4
[BIP] squad gap = AM (delta Q = 0.183)
```

## Data

* **Synthetic generator** (`athletiq.data.synthetic`) — deterministic,
  position-aware archetypes; used by all unit tests and the default seed.
* **StatsBomb Open Data** (`athletiq.data.statsbomb`) — optional, requires
  `pip install -e '.[statsbomb]'`. Loads a match id and aggregates
  per-player vectors matching the synthetic schema.

## Testing

```bash
make test           # fast unit tests
make test-cov       # with coverage
pytest --runslow    # also include slow/cv tests
```

Every paper equation has at least one unit test asserting against a hand-
computed value or a known invariant (e.g. CR = 0 for a perfectly consistent
AHP matrix, WASPAS penalising categorical weakness, BIP respecting budget /
foreign quota).

## Roadmap (v2 seams)

| Area      | Prototype (v1)                           | Research (v2)                              |
| --------- | ---------------------------------------- | ------------------------------------------ |
| Pitch Ctl | Deterministic TTI + logistic             | Full Spearman stochastic TTI               |
| Scouting  | Static PCA/K-Means                       | Online incremental clustering              |
| CV        | Classical keypoint homography + Huber    | Pixel-NeRF refinement (paper §5.4.2)       |
| Re-ID     | ByteTrack default re-id                  | Triplet-loss embedding trained on SoccerNet|
| Deploy    | Cloud only, CPU-friendly                 | TensorRT / ONNX edge, BYTETensor mobile    |
| UI        | English only                             | Full Arabic RTL (i18n scaffolded)          |

## License

Proprietary — AthletIQ Research Division.

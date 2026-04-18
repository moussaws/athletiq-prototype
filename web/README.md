# AthletIQ Web Dashboard

Next.js 14 App Router dashboard for the AthletIQ prototype.

## Dev

```bash
pnpm install
pnpm dev        # :3000 — proxies /backend/* -> http://localhost:8000
```

Make sure the FastAPI backend is running on `:8000` (from the repo root):

```bash
make api
```

## Pages

- `/` — overview
- `/players` — cohort directory with filters
- `/scouting` — cohort grid; click a player to see KNN-similar profiles
- `/scouting/[id]` — similar-player retrieval (hybrid Euclidean+cosine in PCA space)
- `/squad` — AHP pairwise matrix → WASPAS fitness → BIP roster optimization
- `/metrics` — Pitch Control surface visualization (Eq. 7 demo)

## Env

- `ATHLETIQ_API_URL` — backend URL for SSR fetches. Defaults to `http://localhost:8000`.

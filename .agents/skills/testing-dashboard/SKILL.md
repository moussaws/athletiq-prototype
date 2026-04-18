# Testing — AthletIQ dashboard

End-to-end UI + API smoke testing for the Next.js 14 dashboard backed by the FastAPI service.

## Stack layout

- Backend: FastAPI on `127.0.0.1:8000` (run from repo root: `uv run uvicorn athletiq.api.main:app --host 127.0.0.1 --port 8000`).
- Frontend: Next.js 14 dev server on `127.0.0.1:3000` (run from `web/`: `pnpm dev`). It proxies `/backend/*` → `:8000` via `next.config.mjs` rewrites, so the browser only talks to `:3000`.
- Synthetic cohort is built at backend startup: **n=240 players, seed=42, 8 positions (GK/CB/FB/DM/CM/AM/WG/ST)** — deterministic, so fingerprints in tests are stable.

Before starting a recording, maximize Chrome: `wmctrl -r :ACTIVE: -b add,maximized_vert,maximized_horz`.

## Known API shape contracts (enforce or the dashboard crashes)

These all bit us in PR #1 and were fixed in PR #2 — re-check them if anything on these pages goes blank:

- `POST /api/squad` → `{ assignments: [{ position, player_id, name, nationality, age, market_value_m, is_foreign, positional_fit }], total_score, squad_gap_position, squad_gap_delta, budget_used, foreign_count }`. **Not** `lineup`, **not** `score`, **not** nested `squad_gap: {...}`.
- `GET /api/pitch-control/demo` → `{ phi: number[][], xs: number[], ys: number[] }`. No `mean`, no `grid_shape` — the dashboard derives those client-side from `phi.length` / `phi[0].length`.
- `GET /api/scouting/similar/:id` → `{ query_player_id: string, lam: number, results: [...] }`. No full `query: Player` object — the page fetches `/api/players/:id` in parallel to populate the query card.
- `/api/squad` is a two-step flow: first `POST /api/squad/ahp` with the pairwise matrix to get `weights` + `cr`, then `POST /api/squad` with `criteria`, `weights`, `formation`, `budget`, `foreign_max`.

## Smoke plan (8 tests, ~3 min)

Each test has a concrete fingerprint — if the string doesn't match, something regressed.

1. **Home** (`/`) — 4 pillar cards: Metrics, Scouting, Squad, Players.
2. **Players** (`/players`) — footer "60 of 240 players"; P0000 = `GK · Algeria · 17y · €4.6M · yes`.
3. **Filter** (`/players?position=GK`) — "30 of 30 players", every row Pos=GK.
4. **Scouting detail** (`/scouting/P0000`) — query card "Player 0000 · GK · Algeria · 17y · €4.6M"; 10 similar rows; first P0048 sim=0.874.
5. **Squad default** (`/squad`, click optimize) — CR=-0.000, 11-row XI, `Q = 7.917 · €36.4M used · 6 foreigners · gap: FB (Δ0.191)`, GK=Player 0056 (score 0.742, €1.0M, yes).
6. **Squad skewed** — set `pabr × xt_carry = 9`, optimize again. Expect pabr → 34.9%, xt_carry → 12.2%, CR=0.148 (INCONSISTENT flag visible), `Q=8.219 · €38.9M · gap: AM (Δ0.145)`.
7. **Metrics** (`/metrics`) — caption `grid 34×52 · mean 0.555` + SVG heatmap with pitch markings. Mean is computed in the browser; if it reads `NaN` the `phi/xs/ys` contract broke.
8. **Nav sanity** — Metrics → Home → Scouting, no 404s.

When the deterministic fingerprints (0.555, 0.742, Δ0.191, Δ0.145, etc.) drift, the synthetic seed changed — check `src/athletiq/data/synthetic.py` for `n=240, seed=42`.

## Verifying without the UI

Fast pre-flight — these should all return 200 and match the shapes above:

```sh
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/api/pitch-control/demo | jq '{rows: (.phi|length), cols: (.phi[0]|length)}'
curl -s http://127.0.0.1:8000/api/scouting/similar/P0000?k=10 | jq '{q: .query_player_id, n: (.results|length)}'
curl -s -X POST http://127.0.0.1:8000/api/squad/ahp -H 'content-type: application/json' \
  -d '{"criteria":["pabr","xt_carry","ddi","interceptions","passes_completed"],"matrix":[[1,1,1,1,1],[1,1,1,1,1],[1,1,1,1,1],[1,1,1,1,1],[1,1,1,1,1]]}' | jq
curl -s -X POST http://127.0.0.1:8000/api/squad -H 'content-type: application/json' \
  -d '{"criteria":["pabr","xt_carry","ddi","interceptions","passes_completed"],"weights":[0.2,0.2,0.2,0.2,0.2],"formation":{"GK":1,"CB":2,"FB":2,"DM":1,"CM":2,"AM":1,"WG":1,"ST":1},"budget":800,"foreign_max":6}' | jq '{n: (.assignments|length), gap: .squad_gap_position, delta: .squad_gap_delta}'
```

## Recording tips

- `record_annotate` is a **separate** tool call, not an action inside an `act` array. Attempting the latter errors with "Invalid action: record_annotate".
- Use `type="test_start"` to label each T# in the video, and one `type="assertion"` (with `test_result="passed"|"failed"|"untested"`) per test to produce a skimmable report.
- Keep the recording to a single take. Stop before posting the GitHub comment so the video isn't padded by terminal work.

## Devin secrets needed

None — this skill is fully local (backend + frontend on `127.0.0.1`, synthetic data, no external APIs).

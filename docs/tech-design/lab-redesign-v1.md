# Technical Design: Counterfactual Lab v1 — Coach-Credible Foundation

**Status**: Draft
**Author**: Mohamed Samy Moussa (Tech Lead hat) — drafted with Claude
**Date**: 2026-04-19
**PRD**: [`docs/specs/lab-redesign-v1.md`](../specs/lab-redesign-v1.md)
**Tracker**: [athletiq-prototype#25](https://github.com/moussaws/athletiq-prototype/issues/25)
**Related decisions**: [AgDR-0001 — Claude LLM](../agdr/AgDR-0001-llm-provider-for-lab-prescription.md), [AgDR-0002 — StatsBomb Open data](../agdr/AgDR-0002-opponent-data-source.md)

---

## Overview

### Summary

Extend the existing Pitch Control + scenario engine to be **player-conditional and opponent-aware**, and clean up the coach-facing UI surface. No new architectural patterns — every change is a typed extension of an existing module. No new vendor SDK in v1 (`anthropic` from AgDR-0001 lands with Pillar 4, not here).

### Goals

- Lineup actually moves the simulation (per-player kinematics + per-player xG conditioning).
- Opponent selectable from a dropdown; defender posture sampled from the chosen opponent's actual distribution.
- `/lab` lands with a meaningful headline, in coach vocabulary, in ≤ 5 s.
- All open-data reads gated by `ATHLETIQ_LICENSE_TIER` so we cannot accidentally ship the open-data path to a paying customer.

### Non-Goals

- Pillar 4 prescription LLM (Phase 4 — separate tech design once v1 lands).
- Real confidence intervals (Phase 7).
- New compute primitives (no GPU, no async pipeline; we stay numpy + FastAPI).
- Any change to the `/scouting`, `/squad`, `/recruit`, `/cv`, `/matches`, `/metrics` surfaces beyond a P1 deep-link from `/scouting/[id]`.

---

## Domain Model

### New entities

```
PlayerProfile (new)
├── player_id: str            # FK → Player.player_id
├── season: str               # e.g. "2023-24"  (composite PK with player_id)
├── pressing_pct: float                # 0–100 percentile vs position pool
├── progressive_pass_pct: float
├── aerial_duel_win_pct: float
├── finishing_pct: float
├── source: str               # "fbref-2023-24" | …
└── ingested_at: datetime
```

**Deferred from v1** (added when a real tracking source lands — paid feed per AgDR-0002 v2, or our own Pillar C CV when production-grade): `max_speed_ms: float`, `max_accel_ms2: float`. FBRef does not publish tracking-derived signals (verified — see `src/athletiq/data/fbref.py:9-15`), so deriving them from on-ball-activity proxies would be honest only with a derivation citation that adds noise without value. The "lineup actually moves the numbers" requirement is met in v1 entirely via the tactical-percentile xG conditioning below.

```
OpponentProfile (new — domain type, not a DB row in v1)
├── opponent_id: str          # slug, stable across runs (e.g. "atletico-2018-19")
├── display_name: str         # "Atlético Madrid — La Liga 2018-19"
├── source_attribution: str   # "StatsBomb Open Data — CC BY-NC-SA 4.0"
├── formation_mix: list[(formation, weight)]   # e.g. [("4-4-2", 0.7), ("4-2-3-1", 0.3)]
├── def_line_height_distribution: HistogramSamples
├── pressing_intensity_per_zone: 4×3 grid of percentiles
├── positional_heatmap: 34×52 grid (attacker side, normalised to 1)
└── transition_speed_proxy: float       # m/s of opp ball velocity in transition phase
```

### Value objects

| Value object | Fields | Purpose |
|---|---|---|
| `TacticalProfile` | `pressing_pct, progressive_pass_pct, aerial_duel_win_pct, finishing_pct` | Per-player override for `scenario_xg` weights |
| `HistogramSamples` | `bins: list[float]`, `counts: list[int]` | Compact representation of a distribution; sampling is one numpy call |
| `OpponentDefenderSample` | `formation: str`, `defenders: list[Point]`, `def_line_height: float` | One realisation drawn from an `OpponentProfile` for a scenario |

**Deferred** — `KinematicProfile (v_max_ms, reaction_s)` for per-player TTI conditioning. Re-enters when a real tracking source lands (see PlayerProfile note above).

### Domain events

None in v1. Pillar 4 will introduce `ScenarioPrescriptionRequested`; out of scope here.

---

## Architecture

### Component diagram (deltas only)

```
                       ┌─────────────────────────────────┐
                       │  Frontend (Next.js)             │
                       │                                 │
   /lab?v=2 ───────────►  ScenarioLab.tsx                │
                       │   ├─ OpponentPicker  (NEW)      │
                       │   ├─ ScenarioPitch              │
                       │   ├─ ScenarioHeadline (eager)   │
                       │   ├─ ScenarioDiffCards          │
                       │   └─ AnalystView (collapsed)    │
                       │                                 │
                       └────────────┬────────────────────┘
                                    │ POST /api/pitch-control/scenario
                                    │   + attacker_player_ids[]   (NEW)
                                    │   + defender_player_ids[]   (NEW)
                                    │   + opponent_id             (NEW)
                                    ▼
                       ┌─────────────────────────────────┐
                       │  FastAPI                        │
                       │                                 │
                       │   routes/pitch_control.py       │
                       │     ├─ resolves player profiles │
                       │     ├─ samples opponent posture │
                       │     └─ calls phi_from_positions │
                       │                                 │
                       │   data/opponents/  (NEW)        │
                       │     ├─ store.py    (interface)  │
                       │     ├─ statsbomb_open.py        │
                       │     ├─ license_gate.py          │
                       │     └─ profiles_cache.py        │
                       │                                 │
                       │   metrics/pitch_control.py      │
                       │     UNCHANGED in v1             │
                       │     (TTI per-player kinematics  │
                       │      deferred — needs tracking) │
                       │                                 │
                       │   metrics/scenario_xg.py        │
                       │     player-conditional weights  │
                       │     (the v1 lever)              │
                       └─────────────────────────────────┘
                                    │
                                    │ statsbombpy (at startup, cached)
                                    ▼
                       ┌─────────────────────────────────┐
                       │  StatsBomb Open Data            │
                       │  (CC BY-NC-SA 4.0, internal)    │
                       └─────────────────────────────────┘
```

### Data flow

1. `/lab?v=2` mounts. `OpponentPicker` issues `GET /api/opponents` → list of `(opponent_id, display_name)`. Default option is `null` (= generic mirror, current behaviour).
2. On opponent select, frontend issues `GET /api/opponents/{id}` → `OpponentProfile`. Frontend draws an `OpponentDefenderSample` from `formation_mix + def_line_height_distribution` (sampling stays client-side so subsequent edits don't re-fetch).
3. Lineup state already tracks `player_id` per slot. Frontend now sends `attacker_player_ids` (and a default `defender_player_ids` derived from opponent's typical XI when an opponent is loaded) on every `POST /api/pitch-control/scenario`.
4. Backend resolves each `player_id → TacticalProfile`. Missing profiles fall back to the existing global constants — backwards compatible.
5. `phi_from_positions` is unchanged in v1 — TTI uses the existing global `v_max` / `reaction_s`. Per-player kinematic conditioning is deferred (see PlayerProfile note above).
6. `scenario_xg` uses the attacking-side striker's `finishing_pct` to scale shot quality, and the defender's `pressing_pct + aerial_duel_win_pct` to scale `xg_against` recovery. **This is the only math change in v1**, and it's the lever that makes lineup edits move the diff cards.
7. Response shape gains optional `confidence: {tier: "low"|"medium"|"high", reason: str}` — placeholder values in v1; real CIs in Phase 7.
8. `ScenarioHeadline` renders the engine-generated headline on landing (today it suppresses until `edited`). Coach-vocabulary labels for diff cards are mapped client-side via a new `web/src/lib/labCopy.ts` module.

---

## API Design

### New endpoints

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| GET | `/api/opponents` | List available opponent profiles | None (v1 demo-only) |
| GET | `/api/opponents/{id}` | Fetch a single `OpponentProfile` (full payload) | None (v1 demo-only) |

### Modified endpoint

| Method | Path | Change |
|--------|------|--------|
| POST | `/api/pitch-control/scenario` | Request gains 3 optional fields; response gains `confidence` and `lineup_effect` blocks (both optional) |

### Request / response examples

**`POST /api/pitch-control/scenario`** — extended request

```json
{
  "attackers": [{"x": 30, "y": 12}, …],
  "defenders": [{"x": 75, "y": 12}, …],
  "ball": {"x": 52.5, "y": 34},
  "grid_rows": 34,
  "grid_cols": 52,
  "baseline": { … },
  "attacker_player_ids": ["fbref:abc123", null, null, "fbref:xyz789", …],
  "defender_player_ids": null,
  "opponent_id": "atletico-2018-19"
}
```

Extended response (additions only):

```json
{
  "phi": [[…]],
  "diff": { … },
  "zonal": { … },
  "confidence": {
    "tier": "medium",
    "reason": "Built from opponent's last 6 matches in StatsBomb Open Data (2018-19 La Liga)."
  },
  "lineup_effect": {
    "applied": true,
    "missing_profiles": ["fbref:xyz789"],
    "kinematic_overrides_applied": 9,
    "tactical_overrides_applied": 9
  }
}
```

`lineup_effect` is the single best diagnostic for the "lineup actually moves the math" goal — both for tests and for a hover tooltip in the Analyst view.

### Error responses

| Status | Code | When |
|---|---|---|
| 400 | `INVALID_INPUT` | Validation failed (existing) |
| 403 | `LICENSE_TIER_VIOLATION` | An open-data read attempted in production env (gate fired) |
| 404 | `OPPONENT_NOT_FOUND` | `opponent_id` doesn't exist in the registered store |
| 500 | `INTERNAL_ERROR` | Server error (existing) |

---

## Data Model

### `PlayerProfile` storage

SQLite (existing) for v1, since profiles are tiny (~30 numeric fields × few thousand rows). Schema:

```
CREATE TABLE player_profile (
    player_id  TEXT NOT NULL,
    season     TEXT NOT NULL,
    pressing_pct      REAL NOT NULL,
    progressive_pass_pct REAL NOT NULL,
    aerial_duel_win_pct  REAL NOT NULL,
    finishing_pct        REAL NOT NULL,
    source     TEXT NOT NULL,
    ingested_at TIMESTAMP NOT NULL,
    PRIMARY KEY (player_id, season),
    FOREIGN KEY (player_id) REFERENCES player(player_id)
);
CREATE INDEX idx_player_profile_player ON player_profile(player_id);
```

When kinematic absolutes re-enter (post-tracking-source), they'll be added via a follow-up Alembic migration — `ALTER TABLE player_profile ADD COLUMN max_speed_ms REAL` etc. SQLite handles ADD COLUMN cheaply, so leaving them out of v1 is not a forward-compat problem.

This is the v1 migration. Per the migration gate (workflow-gates §3a), this requires a **migration ticket + migration AgDR** before any of the migration files are touched. Use `/migration` when starting Phase 1.

### `OpponentProfile` storage

**v1**: built at ingestion time from StatsBomb Open Data, serialised to JSON files at `data/opponents/<opponent_id>.json`, loaded into an in-process LRU cache on first request. Not in SQLite — they're large-ish (5–50 KB each), versioned in the repo, reproducible from the ingestion script.

**v2 (deferred)**: when paid feeds land, this becomes a real DB table with periodic refresh.

### Access patterns

| Access pattern | Implementation |
|---|---|
| Resolve a player's profile by ID | Primary-key lookup; v1 uses an in-memory dict loaded at startup (816 players) |
| List all opponents | Directory scan of `data/opponents/*.json` at startup, cached |
| Get one opponent by ID | LRU cache (size 16; opponents are small enough) |

---

## Implementation Plan

Tasks ordered by Phase. Each task = one PR's worth of work; tests included in the estimate.

### Phase 0 — Foundation cleanup

| # | Task | Estimate | Dependencies |
|---|------|----------|--------------|
| P0-1 | Add `?v=2` feature flag wiring in `web/src/app/lab/page.tsx`; default `v=1` reads existing `ScenarioLab`, `v=2` reads new `ScenarioLabV2` (initially identical, will diverge in subsequent tasks) | 0.5d | — |
| P0-2 | Render baseline insight on landing — modify `ScenarioHeadline` to emit the headline whenever `diff` is non-null, regardless of `edited` | 0.5d | P0-1 |
| P0-3 | Create `web/src/lib/labCopy.ts` with the coach-vocabulary mappings (Φ → "Attack pressure", Δ → "Change", etc.) and refactor `ScenarioDiffCards.tsx` to read labels from it. Keep the technical labels available for the Analyst view via a `mode` prop | 1d | P0-1 |
| P0-4 | Strip `web/src/app/lab/page.tsx` header — remove the academic citation footer + the inline Greek-letter prose (move to a new "About this Lab" tooltip / sidebar) | 0.5d | — |
| P0-5 | Add the confidence pill component with hard-coded text (`"Confidence: medium — based on opponent's last 6 matches"`) — accept `confidence` from the API response, fall back to a default when absent | 0.5d | P0-1 |
| P0-6 | Backend: extend `ScenarioResponse` with optional `confidence` block; populate with the placeholder when an opponent is loaded, omit otherwise | 0.5d | — |
| **Total Phase 0** | | **3–4 days** | |

### Phase 1 — Player tactical profile (kinematics deferred per resolved Open Q #2)

| # | Task | Estimate | Dependencies |
|---|------|----------|--------------|
| P1-1 | Run `/migration` to create the migration ticket + AgDR for `player_profile`. Then write the Alembic migration | 0.5d | (gate) |
| P1-2 | Add `TacticalProfile` value object in `src/athletiq/scouting/types.py`. Pydantic model for API serialisation | 0.5d | — |
| P1-3 | FBRef percentile ingestion script `scripts/ingest_player_profiles.py` — reads the existing FBRef CSV the seed pipeline uses, computes 4 percentile fields per position pool (`pressing_pct`, `progressive_pass_pct`, `aerial_duel_win_pct`, `finishing_pct`), writes to `player_profile`. No m/s derivation. | 1d | P1-1 |
| P1-4 | Extend `scenario_xg` to weight shot quality by attacker-side `finishing_pct` and recovery by defender-side `pressing_pct + aerial_duel_win_pct`. Document the math in the docstring; include the formula change in the PR description. **The single math change in v1.** Add unit tests asserting (a) absent profiles match the existing baseline within 1e-12 and (b) a high-`finishing_pct` swap visibly raises `xg_for` in the expected direction. | 2d | P1-2 |
| P1-5 | Extend `phi_from_positions` API to accept `attacker_profiles` and `defender_profiles` lists. Resolve them in the route handler from `attacker_player_ids` / `defender_player_ids`. **Note**: `phi_from_positions` itself doesn't use the profiles in v1 — it just plumbs them through to `scenario_xg`. | 1d | P1-2, P1-4 |
| P1-6 | Wire `attacker_player_ids` / `defender_player_ids` into the `/api/pitch-control/scenario` request schema; add `lineup_effect` to the response | 0.5d | P1-5 |
| P1-7 | Frontend: send player IDs from `ScenarioLabV2` whenever the lineup has non-null entries; remove the `"Lineup travels in the share link; Φ math is unaffected"` disclaimer text | 0.5d | P1-6 |
| P1-8 | Hover tooltip on each lineup slot showing the player's tactical percentiles — small `<Popover>` component | 1d | P1-2, P1-7 |
| **Total Phase 1** | | **6–7 days** | |

### Phase 2 — Opponent profile v0

| # | Task | Estimate | Dependencies |
|---|------|----------|--------------|
| P2-1 | Scaffold `src/athletiq/data/opponents/` package: `store.py` (interface), `__init__.py`, `license_gate.py`, `profiles_cache.py`. `OpponentEventStore` is a Protocol with `list_opponents()`, `get_profile(id)`, `attribution_text()` | 0.5d | — |
| P2-2 | Implement `license_gate.py` — fail-closed check on `ATHLETIQ_LICENSE_TIER` × `ATHLETIQ_ENV`. Decorator-friendly so any new store implementation is gated by a one-line annotation. **Includes the unit test asserting closed-fail when both vars unset** | 1d | P2-1 |
| P2-3 | Implement `StatsBombOpenStore` — uses `statsbombpy`, ingests N opponents at construction, builds `OpponentProfile` per opponent, persists to `data/opponents/*.json` | 3d | P2-1, P2-2 |
| P2-4 | Run the ingester for the 2 v1 opponents (resolved per Open Q #1: **Bayer Leverkusen Bundesliga 2023-24** + **Spain Euro 2024**, both verified with full coverage), commit the JSONs | 1d | P2-3 |
| P2-5 | API routes `GET /api/opponents` and `GET /api/opponents/{id}` in a new `routes/opponents.py`. Wire to the cached store | 0.5d | P2-3 |
| P2-6 | Backend: when `opponent_id` is sent on a scenario request, sample defender posture from the opponent's `formation_mix + def_line_height_distribution` instead of mirroring the attacker formation | 1.5d | P2-5 |
| P2-7 | Frontend: `OpponentPicker.tsx` component — dropdown above the formation row with "No opponent (generic)" as the default plus the 2 shipped options ("Bayer Leverkusen — Bundesliga 2023-24" and "Spain — Euro 2024"). Wire to `GET /api/opponents` | 1d | P2-5 |
| P2-8 | Frontend: when an opponent is selected, fetch the profile and pass it into `ScenarioLabV2` to drive the initial defender posture and the confidence-pill text. Ensure `?opp=<id>` param is preserved in share links | 1d | P2-7 |
| P2-9 | Frontend: license attribution line `"StatsBomb Open Data — CC BY-NC-SA 4.0"` rendered when an opponent is loaded; clicking it opens a brief explainer modal | 0.5d | P2-7 |
| P2-10 | End-to-end smoke test: start API + web, select Bayer Leverkusen 2023-24, swap a high-`finishing_pct` forward into the lineup, assert that the `xg_for` diff card visibly increases. Run on CI | 1d | all P2 |
| **Total Phase 2** | | **10–12 days** | |

### Cross-cutting

| # | Task | Estimate |
|---|------|----------|
| X-1 | When `?v=2` becomes default (post Phase 2 design-partner validation), delete `ScenarioLab.tsx` and rename `ScenarioLabV2.tsx`. One PR, no behaviour change. | 0.5d |
| X-2 | Add `ATHLETIQ_LICENSE_TIER`, `ATHLETIQ_ENV`, `STATSBOMB_OPEN_DATA_PATH` to a new `.env.example` (resolves the prototype's missing-env-example finding from the handover assessment) | 0.5d |

**Grand total** (single engineer): **20–24 days** — fits the PRD's tightened 2.5–4 weeks once you account for review cycles and parallelisable Phase 0/1 work. Phase 1 dropped from 10–12 days to 6–7 days after Open Q #2 was resolved (no FBRef m/s derivation, no per-player TTI extension).

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| ~~FBRef physical data doesn't expose absolute m/s~~ | — | — | **Removed**: Open Q #2 resolved by skipping kinematic absolutes from v1 entirely. The risk no longer exists. |
| StatsBomb Open coverage of the 2 chosen opponents was too thin (Atlético had only 2 matches per season) | Confirmed | Was Med | **Resolved**: chose Bayer Leverkusen 2023-24 (34 matches) + Spain Euro 2024 (7 tournament matches) instead. Both verified live with full coverage. |
| Per-player tactical conditioning regresses scenario latency past the 100 ms target | Low | Low | The math is a small number of scalar multiplies inside the existing tensor pipeline; profile P1-4 with `pytest-benchmark` and assert no regression in CI |
| `ATHLETIQ_LICENSE_TIER` gate gets bypassed in some unusual code path (a script, a notebook, a one-off CLI) | Low | High (legal) | Gate sits at `OpponentEventStore` construction, not at `__init__.py` import — every consumer must go through the constructor; review checklist includes "did this PR add a new opponent-data read path?" |
| Brand cleanup is contested (research lead wants Greek letters preserved on the public surface) | Med | Low | Per PRD Open Q #5: keep Greek letters + citations in the Analyst view; agree this in writing before P0-3 + P0-4 land. Mitigation cost is one short conversation, not a redesign |
| `?v=2` ships with a regression vs `?v=1` not caught by tests | Med | Low | Both routes available for the first 1–2 sessions; explicit comparison in the smoke test (P2-10); rollback is removing the `?v=2` route, ~5 min |
| Migration for `player_profile` blocks because the migration AgDR isn't written | High (process) | Med | P1-1 explicitly runs `/migration` first; this is a known gate, not a surprise |

---

## Security Considerations

- [x] No new authentication surface — v1 is internal/demo only, matches the rest of the FastAPI app's posture (no auth today; flagged in the handover assessment as a P0 gap before any external pilot, but **out of scope for this PRD**)
- [x] Input validation at the new endpoints — Pydantic models on every request body
- [x] License gate on opponent-data reads (the actual security-adjacent concern in v1)
- [x] No PII added — player profiles are public stats; opponent profiles are public match data
- [x] No secrets — `STATSBOMB_OPEN_DATA_PATH` is a filesystem path, not a credential
- [ ] **Security Auditor review NOT triggered for v1** — no auth/crypto/secrets/PII files touched (per `.claude/rules/role-triggers.md`). When Pillar 4 adds the LLM call with user-supplied opponent data, that PR will trigger the review.

---

## Testing Strategy

| Type | Coverage | Notes |
|---|---|---|
| Unit | All math changes, > 90% | Per-player TTI extension (P1-4); player-conditional xG (P1-6); license gate closed-fail (P2-2) |
| Integration | Each new route + the modified `/api/pitch-control/scenario` | Fixture-driven; `StatsBombOpenStore` runs against a small committed fixture, not live data |
| End-to-end | One critical flow | P2-10 — load Atlético, swap a player, assert diff cards change. Runs on CI. |
| Performance | Pitch Control regression check | `pytest-benchmark` baseline before P1-4 lands; assert Phase 1 + Phase 2 stay within +10% of that baseline |

---

## Open Questions

| Question | Owner | Status |
|---|---|---|
| Which 2 opponents ship for v1? (PRD Open Q #1) | Mohamed + Tech Lead | **Resolved 2026-04-19**: Bayer Leverkusen Bundesliga 2023-24 + Spain Euro 2024 (verified live coverage) |
| FBRef physical-data shape — absolute or derived? (PRD Open Q #2) | Backend + Data | **Resolved 2026-04-19**: dropped from v1; tactical percentiles only (no `max_speed_ms` / `max_accel_ms2` until a real tracking source lands) |
| Coach contact for early validation (PRD Open Q #3) | Mohamed | Open — not blocking v1 implementation but blocks design-partner session at end of Phase 2 |
| Scouting → Lab deep link in v1 P0 or v1 P1? (PRD Open Q #4) | Mohamed | P1 in PRD; promote to P0 only if a design partner asks |
| Brand cleanup sign-off (PRD Open Q #5) | Mohamed + research lead | Open — get agreement in writing before P0-3 / P0-4 land |
| Set-piece tendencies in `OpponentProfile`? (PRD Open Q #6) | Backend | **Recommend dropping from v1** — StatsBomb Open's set-piece coverage is thin; add when paid feed lands |

---

## Approvals

| Role | Name | Date | Status |
|---|---|---|---|
| Tech Lead | Mohamed Samy Moussa | 2026-04-19 | **Author** |
| Head of Engineering | — | — | **Not required** — no new architecture, no new tech stack, no new external integration beyond what's already optional in pyproject. Per role-triggers, escalation is for "new service / external integration / new technology / major data model change" — `player_profile` table addition is small enough not to qualify. If anyone disagrees, escalate. |
| Security Auditor | — | — | **Not required for v1** — see Security Considerations. Required when Pillar 4 lands. |

---

## Handoff to engineers

When this design is approved, the next steps:

1. **Break P0/P1/P2 tasks into individual GitHub Issues** in `moussaws/athletiq-prototype`, all linked to athletiq-prototype#25 and labelled `lab-v1` + (`phase-0` | `phase-1` | `phase-2`). One issue = one PR.
2. **P1-1 must come before any other Phase 1 task** — it's the migration gate.
3. **Phase 0 can be parallelised** with Phase 1 setup (P1-2, P1-3) since they touch different files.
4. **Phase 2 requires Phase 1 P1-2 + P1-7 done** (the new value objects + extended `phi_from_positions`).

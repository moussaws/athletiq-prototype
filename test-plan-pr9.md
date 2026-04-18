# PR #9 test plan — coach-facing match narrative + tape-view readout

**PR**: https://github.com/moussaws/athletiq-prototype/pull/9
**Branch**: `devin/1776537505-ux-r2-match-tape-coach` (head `b354c2b` after Devin Review fix)

## What changed

Two coach-facing screen reworks:

1. **Match page** (`/matches/match/[id]`) — leads with an emerald **Coach headline** strip + per-team cards (one-sentence team summary, 5 stat tiles, role-tagged Top performers: Creator / Ball carrier / Finisher / Defensive worker / Passer). Raw per-player event tables tucked behind an `Analyst view` `<details>` toggle. New backend endpoint `/api/statsbomb/match/{id}/insights`.
2. **Tape view** (`/cv`) — page retitled "Tape view — from footage to pitch", new emerald **Coach readout** card translates detection/tracking/projection numbers into plain-English shape verdicts (compact block vs stretched; narrow vs full-width). Raw `fps` / `resolution` / `detections` / `unique tracks` / `projected` moved behind `Analyst view`. Nav label `CV pipeline` → `Tape view`. Homepage cards reworded.

Evidence from code tracing:
- Backend narrative builder — <ref_snippet file="/home/ubuntu/repos/athletiq-prototype/src/athletiq/insights/match.py" lines="81-120" /> (`_top` + `_verbalise`, incl. Devin Review fix).
- New endpoint — <ref_snippet file="/home/ubuntu/repos/athletiq-prototype/src/athletiq/api/routes/statsbomb.py" lines="208-289" />.
- Match page UI — <ref_snippet file="/home/ubuntu/repos/athletiq-prototype/web/src/app/matches/match/[match_id]/page.tsx" lines="24-90" />.
- TapeReadout component — <ref_snippet file="/home/ubuntu/repos/athletiq-prototype/web/src/app/cv/page.tsx" lines="375-460" />.

## Primary flow

**T1 — Match narrative end-to-end**: Home → `/matches` → pick *FIFA World Cup · 2022* → open *Qatar vs Ecuador (0-2)*. Verify coach-first UX: headline names Ecuador as dominant; each team card shows a summary sentence + 5 stat tiles + 5 role-tagged performer rows with sensible verdicts. Expand Analyst view and verify the raw per-player tables come back.

**T2 — Tape view coach readout**: `/cv` (nav label reads "Tape view"). Upload `0bfacc_0.mp4` with `include_homography=true`. Verify the emerald Coach readout card generates shape-depth/width verdicts and 3 stat tiles (On screen / Shape depth / Shape width). Expand Analyst view and verify the raw counters are still available.

## Key assertions

### T1 · Match narrative (Qatar 0-2 Ecuador, match_id 3857286)

Live API evidence baked into expected values (from `curl .../insights` on HEAD of feature branch):

| Assertion | Expected (exact) | Why it fails if broken |
|---|---|---|
| T1.1 Coach headline | Emerald banner contains the exact string `"Ecuador controlled territorial threat over Qatar"` | If the new `/insights` endpoint isn't wired, page falls back to the old layout and there's no green banner — or headline says "evenly-matched" (threshold bug). |
| T1.2 Qatar team card | Summary starts with "They struggled to progress the ball into high-threat zones". Stat tiles show **xT carry = 1.28**, **Shots = 5**, **Take-ons = 15**, **Passes = 382**, **Tackles+Int = 29**. | Raw numbers regenerate team totals wrong if aggregation dropped NaN-safe handling or the endpoint returns stale data. |
| T1.3 Ecuador team card | Summary contains "carried the ball into dangerous areas far more than their opponent" and "won the defensive exchanges (41 tackles+interceptions)". Stat tiles: **xT carry = 1.74**, **Shots = 6**, **Passes = 432**, **Tackles+Int = 41**. | Team story heuristic thresholds (xT 1.15×, def 1.2×) need to both be satisfied for this dual-clause summary. |
| T1.4 Qatar top performers | 5 rows in order: **Creator** `Akram Hassan Afif (CM)` verdict contains `"0.28 xT"`; **Ball carrier** `Akram Hassan Afif (CM)`; **Finisher** `Almoez Ali Zainalabiddin Abdulla (CM)` verdict contains `"(1)"`; **Defensive worker** `Boualem Khoukhi (CB)` verdict contains `"5 tackles + interceptions"` (post-fix combined metric); **Passer** `Boualem Khoukhi (CB)` verdict contains `"(66)"`. | If the Devin Review fix regressed, DW verdict would read `"4 tackles + interceptions"` (just tackles). If `_top` broke, rows would be blank or wrong player. |
| T1.5 Ecuador top performers | **Creator** `Romario Andrés Ibarra Mina (CM)` verdict contains `"0.44 xT"`; **Defensive worker** `Michael Steveen Estrada Martínez (CM)` verdict contains `"8 tackles + interceptions"`. | Same check applied across a second team with different DW combined value (8, not 5). |
| T1.6 Analyst view toggle | `<details>` labeled "Analyst view" is initially collapsed. Click to expand → two per-team tables render with rows for every player (Qatar ≥ 13, Ecuador ≥ 15), columns `#` `Player` `Pos` `Passes` `Shots` `Take-ons` `Tackles` `xT` `Progressive`. Coverage callout mentions imputed features: `aerial_duels_won, sprint_count, accel_count, pabr, ddi`. | If the toggle state broken, analyst view either stays hidden, is open by default (regression), or collides with the coach cards above. |

### T2 · Tape view coach readout

Baked-in expected values from direct `analyze_video('0bfacc_0.mp4', max_frames=30, conf=0.25, include_homography=True)` call (Bundesliga broadcast, 1920×1080): ~257 detections, 14 unique tracks, 100% projection at default keypoints (1920×1080 native match).

| Assertion | Expected (exact) | Why it fails if broken |
|---|---|---|
| T2.0 Nav + title | Left-hand nav shows `"Tape view"` (not `"CV pipeline"`). H1 on `/cv` reads `"Tape view — from footage to pitch"`. | Nav/title regression would indicate the route metadata didn't update. |
| T2.1 Coach readout card rendered | Emerald card titled **"Coach readout"** is visible above the raw stats/table area. First line matches regex `/^Tracked \d+ distinct figures? across \d+ frames? — on average [\d.]+ on screen\.$/` with tracked ≥ 8. | If `TapeReadout` isn't wired or `tracks` / `frames` computations broken, line is missing or reads `NaN`/`Infinity`. |
| T2.2 Shape verdict line (projection ON) | Second line matches `/On the pitch the side showed .* ≈\d+ m deep .* ≈\d+ m wide/`. At least one of the verdict adjectives must come from the hard-coded set: `"very compact block defensively"`, `"balanced vertical shape"`, `"stretched shape with defenders and attackers far apart"`, `"narrow horizontally"`, `"reasonable horizontal spread"`, `"full width of the pitch used"`. | If `inside.length ≤ 1` or projection flag off, this line is replaced by the "tick pitch-projection" nudge — visible failure. |
| T2.3 Readout stat tiles | 3 tiles render under the readout: `On screen` with a numeric value, `Shape depth` ending in `" m"`, `Shape width` ending in `" m"`. | If the `hasProjection && inside.length > 1` branch doesn't fire, tiles don't render. |
| T2.4 Analyst view toggle | `<details>` labeled `"Analyst view"` collapsed by default. Expand → 5 raw stat cards visible: `fps`, `resolution` (contains "1920×1080"), `detections` (≥ 100), `unique tracks` (≥ 5), `projected` (format `"N (100%)"`). | If analyst view is open by default the coach-first framing is broken; if stats missing the movement from top-level to `<details>` was incomplete. |

## Adversarial redesign check

For every assertion above: **would a broken/reverted implementation produce the same screen?**
- T1.1 — no. A revert leaves the old match page without an emerald banner at all.
- T1.2/T1.3 — no. Totals come from a new endpoint; a revert gives 404 on `/insights`.
- T1.4/T1.5 — DW verdicts with exact values `"5 tackles + interceptions"` and `"8 tackles + interceptions"` specifically guard the Devin Review fix (pre-fix they'd be `4` and a different player could win).
- T1.6 — analyst view toggle: if it's removed or inverted, the expand-from-collapsed flow is visibly different.
- T2.0 — nav label `"Tape view"` is a surface-level string check.
- T2.1 — regex would fail against the old raw layout where the line doesn't exist.
- T2.2 — coach verdicts come from a hard-coded set; anything else is a bug.
- T2.3 — tiles only render under a specific data condition.
- T2.4 — ordering (coach before raw) and `<details>` collapsed state is load-bearing.

## Out of scope

- Unit tests (129 already green, +1 regression test for DW fix).
- Scouting / metrics / squad pages (unchanged).
- Performance / load / accessibility.
- Extensive regression across other routes.

## Recording

One continuous browser recording covering T1 then T2. Will use `computer(action="record_annotate")` for setup (nav to matches, open match), `test_start` and `assertion` annotations for each assertion bullet above. Maximize browser before starting.
